import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipIf(ClientSession is None,'Install the mcp extra to test actual stdio transport')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_tool_boundary(self):
        server=StdioServerParameters(command=sys.executable,args=['-B','-m','jev_gtw.cli','serve','--config',str(ROOT/'examples/gateway.json')],
                                     env={'TMPDIR':os.environ['TMPDIR'],'PYTHONPATH':str(ROOT)})
        async with stdio_client(server) as (read,write), ClientSession(read,write) as session:
            await session.initialize()
            listed=await session.list_tools()
            self.assertEqual({t.name for t in listed.tools},{'gateway_sources','gateway_read','gateway_compute'})
            catalog=await session.call_tool('gateway_sources',{})
            self.assertNotIn('person-a@example.test',catalog.model_dump_json())
            setup=await session.call_tool('gateway_read',{'source_id':'setup'})
            self.assertEqual(json.loads(setup.content[0].text)['action'],'show')
            private=await session.call_tool('gateway_read',{'source_id':'records'})
            self.assertEqual(json.loads(private.content[0].text)['action'],'local')
            self.assertNotIn('person-a@example.test',private.model_dump_json())
            image=await session.call_tool('gateway_read',{'source_id':'public_image'})
            self.assertEqual([c.type for c in image.content],['text','image'])
            bad=await session.call_tool('gateway_read',{'source_id':'../../etc/passwd'})
            self.assertEqual(json.loads(bad.content[0].text)['action'],'hold')
            disabled=await session.call_tool('gateway_compute',{'source_ids':['records'],'code':'print(1)'})
            self.assertEqual(json.loads(disabled.content[0].text)['action'],'hold')


class PackagingTests(unittest.TestCase):
    def test_both_skill_installations_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            command=[sys.executable,str(ROOT/'tools/install_skill.py'),'--target','both','--project',temp]
            subprocess.run(command,check=True,capture_output=True)
            for folder in ['.agents','.claude']:
                target=Path(temp)/folder/'skills/jev-gtw'
                self.assertEqual((target/'SKILL.md').read_bytes(),(ROOT/'skills/jev-gtw/SKILL.md').read_bytes())
                self.assertTrue((target/'references/workflow.md').is_file())
            repeat=subprocess.run(command,capture_output=True)
            self.assertNotEqual(repeat.returncode,0)


if __name__=='__main__':unittest.main()
