import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from jev_gtw import Context, Observation, StartLuxJudge
from tests.helpers import png


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.reply={'answers':{'release':{'type':'noul','noul':.99}}};self.redirect=False
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
        StartLuxJudge(self.url)(Context('task','policy'),Observation(image=png()))
        self.assertTrue(self.requests[0]['images'][0].startswith('data:image/png;base64,'))

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
        for reply in [{'type':'choice','choice':'yes'},{'type':'noul','noul':True},{'type':'noul','noul':2}]:
            self.reply={'answers':{'release':reply}}
            with self.assertRaises(ValueError):StartLuxJudge(self.url)(Context('task','policy'),Observation(text='schema'))


if __name__=='__main__':unittest.main()
