import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_gtw import Access, Context, Gateway, Observation
from jev_gtw.service import Service, Source, read_beneath
from jev_gtw.sandbox import Capture
from tests.helpers import Judge, png


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.root/'private.txt').write_text('FICTIONAL_SECRET_492')
        (self.root/'public.txt').write_text('Public task setup.')
        (self.root/'image.png').write_bytes(png())
        public=Observation(text='Public task setup.')
        self.sources={'private':Source('private.txt','text',Access()),
                      'public':Source('public.txt','text',Access('approved',approved_sha256=public.fingerprint())),
                      'image':Source('image.png','png',Access('approved',approved_sha256=Observation(image=png()).fingerprint()))}
        self.ctx=Context('Compute counts.','Records stay local.')
        self.service=Service(self.root,self.ctx,self.sources,Gateway(Judge()))

    def test_protected_read_does_not_open_file(self):
        with patch('jev_gtw.service.read_beneath',side_effect=AssertionError('must not open')):
            result=self.service.read('private')
        self.assertEqual(result['action'],'local');self.assertNotIn('FICTIONAL_SECRET',json.dumps(result))

    def test_public_and_image_views(self):
        self.assertEqual(self.service.read('public')['text'],'Public task setup.')
        self.assertIn('image_base64',self.service.read('image'))

    def test_public_changed_on_disk_is_held(self):
        (self.root/'public.txt').write_text('FICTIONAL_SECRET_492')
        result=self.service.read('public');self.assertEqual(result['action'],'hold')
        self.assertNotIn('FICTIONAL_SECRET',json.dumps(result))

    def test_unknown_source_and_paths_not_echoed(self):
        for handle in ['../../private','/etc/passwd','private.txt','ERROR_SECRET']:
            result=self.service.read(handle);self.assertEqual(result['action'],'hold')
            self.assertNotIn(handle,json.dumps(result))

    def test_symlink_rejected(self):
        (self.root/'link').symlink_to(self.root/'private.txt')
        with self.assertRaises(OSError):read_beneath(self.root,'link',1024)

    def test_symlink_parent_rejected(self):
        (self.root/'folder').mkdir();(self.root/'folder/x').write_text('x')
        (self.root/'alias').symlink_to(self.root/'folder')
        with self.assertRaises(OSError):read_beneath(self.root,'alias/x',1024)

    def test_traversal_and_special_files_rejected(self):
        for path in ['../private.txt','/etc/passwd','./private.txt']:
            with self.assertRaises(ValueError):read_beneath(self.root,path,10)
        os.mkfifo(self.root/'pipe')
        with self.assertRaises(ValueError):read_beneath(self.root,'pipe',10)

    def test_invalid_utf8_and_oversize_fail_closed(self):
        self.service.sources['untrusted']=Source('bad','text',Access('contextual'))
        for raw in [b'\xff',b'x'*96_001]:
            (self.root/'bad').write_bytes(raw)
            self.assertNotEqual(self.service.read('untrusted')['action'],'show')

    def test_no_executor_never_runs_on_host(self):
        result=self.service.compute(['private'],"raise Exception('secret')")
        self.assertEqual(result['action'],'hold')

    def test_probe_capture_inherits_local_policy(self):
        class FakeRunner:
            def run(inner,code,inputs):
                self.assertEqual(inputs,{'private':b'FICTIONAL_SECRET_492'})
                return Capture('FICTIONAL_SECRET_492',True,'f'*32)
        self.service.runner=FakeRunner()
        result=self.service.compute(['private'],'print(...)')
        self.assertEqual(result['action'],'local');self.assertNotIn('FICTIONAL_SECRET',json.dumps(result))

    def test_probe_cannot_override_source_policy(self):
        class Never:
            def run(*_):raise AssertionError('must not execute')
        self.service.runner=Never()
        self.service.sources['private']=Source('private.txt','text',Access('deny'))
        self.assertEqual(self.service.compute(['private'],'print(1)')['action'],'hold')

    def test_probe_exception_not_exposed(self):
        class Failing:
            def run(*_):raise RuntimeError('FICTIONAL_SECRET_492')
        self.service.runner=Failing()
        result=self.service.compute(['private'],'pass')
        self.assertEqual(result['action'],'hold');self.assertNotIn('FICTIONAL_SECRET',json.dumps(result))

    def test_probe_outputs_require_separate_permission(self):
        class FakeRunner:
            def run(*_):return Capture('total = 42',True,'f'*32)
        self.service.runner=FakeRunner()
        self.service.sources['private']=Source('private.txt','text',Access(),'contextual')
        self.assertEqual(self.service.compute(['private'],'pass')['action'],'show')
        self.service.gateway=Gateway(Judge(.2))
        self.assertEqual(self.service.compute(['private'],'pass')['action'],'local')

    def test_configuration_is_host_owned(self):
        config={'version':1,'root':'.','context':{'task':'Compute counts.','policy':'Records stay local.'},
                'sources':{'records':{'path':'private.txt'}}}
        p=self.root/'config.json';p.write_text(json.dumps(config));service=Service.from_config(p)
        self.assertEqual(service.read('records')['action'],'local')
        config['sources']['records']['path']='../private.txt';p.write_text(json.dumps(config))
        with self.assertRaises(ValueError):Service.from_config(p)

    def test_withheld_read_offers_only_configured_navigation(self):
        self.service.sources['private']=Source('private.txt','text',Access(),public_context='public')
        result=self.service.read('private')
        self.assertEqual(result['next_steps'],[{'tool':'gateway_read','arguments':{'source_id':'public'}}])
        self.assertEqual(self.service.read('public')['action'],'show')
        (self.root/'public.txt').write_text('FICTIONAL_SECRET_492')
        self.assertEqual(self.service.read('public')['action'],'hold')

    def test_navigation_does_not_authorize_unapproved_sources(self):
        for target in ['missing','private','image_contextual']:
            sources=dict(self.sources)
            sources['image_contextual']=Source('image.png','png',Access('contextual'))
            sources['private']=Source('private.txt','text',Access(),public_context=target)
            with self.assertRaises(ValueError):Service(self.root,self.ctx,sources,Gateway())

    def test_next_steps_respect_compute_availability_and_denial(self):
        self.service.runner=object()
        self.assertEqual(self.service.read('private')['next_steps'],[{'tool':'gateway_compute','source_ids':['private']}])
        self.service.sources['private']=Source('private.txt','text',Access('deny'))
        self.assertEqual(self.service.read('private')['next_steps'],[{'action':'operator_review'}])

    def test_repeated_views_do_not_displace_relevant_history(self):
        for _ in range(20):self.service.read('public')
        self.assertEqual(self.service.history,['Public task setup.'])


if __name__=='__main__':unittest.main()
