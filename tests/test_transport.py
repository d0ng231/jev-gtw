import json
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch

from jev_gtw import Context, Observation, StartLuxJudge
from tests.helpers import png


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.reply={'answers':{'release':{'type':'noul','noul':.01}}};self.redirect=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                owner.requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if owner.redirect:
                    self.send_response(302);self.send_header('Location','http://example.invalid/capture');self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps(owner.reply).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def test_single_typed_binary_request(self):
        result=StartLuxJudge(self.url)(Context('task','policy'),Observation(text='schema'))
        self.assertEqual(result.permitted,.99);self.assertEqual(len(self.requests),1)
        req=self.requests[0];self.assertEqual(req['think_mode'],'never');self.assertEqual(list(req['questions']),['release'])
        self.assertNotIn('gold',json.dumps(req));self.assertEqual(req['state']['observation'],'schema')

    def test_image_transport(self):
        result=StartLuxJudge(self.url)(Context('task','policy'),Observation(image=png()))
        self.assertTrue(self.requests[0]['images'][0].startswith('data:image/png;base64,'))
        self.assertEqual(result.permitted,.01)

    def test_redirect_never_transmits_to_other_host(self):
        self.redirect=True
        with self.assertRaises(ValueError):StartLuxJudge(self.url)(Context('task','policy'),Observation(text='secret'))
        self.assertEqual(len(self.requests),1)

    def test_unknown_remote_endpoint_rejected(self):
        for url in ['https://example.test','http://example.test','http://localhost/x','http://user:pass@localhost','http://localhost?x=1']:
            with self.assertRaises(ValueError):StartLuxJudge(url)

    def test_explicit_private_host_configuration(self):
        self.assertEqual(StartLuxJudge('http://worker:8090',trusted_hosts=['worker']).url,'http://worker:8090/v1/systemone')

    def test_invalid_answer_does_not_default_to_permit(self):
        for reply in [{'type':'choice','choice':'yes'},{'type':'noul','noul':True},{'type':'noul','noul':2},
                      {'type':'noul','noul':float('nan')},{'type':'noul','noul':'0'},{'type':'noul','noul':-1}]:
            self.reply={'answers':{'release':reply}}
            with self.assertRaises(ValueError):StartLuxJudge(self.url)(Context('task','policy'),Observation(text='schema'))

    def test_legacy_permission_profile_is_explicit(self):
        self.assertEqual(StartLuxJudge(self.url,question_profile='permission')(Context('task','policy'),Observation(text='schema')).permitted,.01)

    def test_exact_repeated_request_uses_cache(self):
        judge=StartLuxJudge(self.url);context=Context('task','policy');observation=Observation(text='schema')
        first=judge(context,observation);second=judge(context,observation)
        self.assertFalse(first.cached);self.assertTrue(second.cached)
        self.assertEqual(first.permitted,second.permitted);self.assertEqual(len(self.requests),1)
        self.assertNotIn('schema',repr(judge._cache))

    def test_cache_binds_context_session_image_and_source(self):
        judge=StartLuxJudge(self.url);context=Context('task','policy');observation=Observation(text='schema')
        judge(context,observation)
        for field,value in [('task','other'),('policy','new'),('recipient','new'),('session','new'),('history',('new',))]:
            self.assertFalse(judge(replace(context,**{field:value}),observation).cached)
        for changed in [replace(observation,text='changed'),replace(observation,image=png()),
                        replace(observation,source='changed'),replace(observation,request='changed'),replace(observation,complete=False)]:
            self.assertFalse(judge(context,changed).cached)
        self.assertEqual(len(self.requests),11)

    def test_cache_expiry_and_eviction(self):
        judge=StartLuxJudge(self.url,cache_size=1,cache_ttl=1);ctx=Context('task','policy')
        with patch('jev_gtw.judge.time.monotonic',return_value=100):
            judge(ctx,Observation(text='first'))
            self.assertTrue(judge(ctx,Observation(text='first')).cached)
        with patch('jev_gtw.judge.time.monotonic',return_value=102):
            self.assertFalse(judge(ctx,Observation(text='first')).cached)
            judge(ctx,Observation(text='second'))
            self.assertFalse(judge(ctx,Observation(text='first')).cached)
        self.assertEqual(len(judge._cache),1)

    def test_failures_are_not_cached(self):
        judge=StartLuxJudge(self.url);ctx=Context('task','policy');obs=Observation(text='schema')
        self.reply={'answers':{'release':{'type':'noul','noul':None}}}
        with self.assertRaises(ValueError):judge(ctx,obs)
        self.reply={'answers':{'release':{'type':'noul','noul':.01}}}
        self.assertFalse(judge(ctx,obs).cached);self.assertEqual(len(self.requests),2)

    def test_cache_can_be_disabled_and_settings_are_bounded(self):
        judge=StartLuxJudge(self.url,cache_size=0)
        for _ in range(2):self.assertFalse(judge(Context('task','policy'),Observation(text='schema')).cached)
        self.assertEqual(len(self.requests),2)
        for options in [{'cache_size':-1},{'cache_ttl':0},{'cache_ttl':float('nan')},{'timeout':float('nan')},{'question_profile':'unknown'}]:
            with self.assertRaises(ValueError):StartLuxJudge(self.url,**options)


if __name__=='__main__':unittest.main()
