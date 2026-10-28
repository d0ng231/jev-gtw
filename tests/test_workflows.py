from pathlib import Path
import tempfile
import unittest

from tools.exercise_workflows import grade_workflow


class WorkflowGradingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.artifact='a'*32
        output=self.root/self.artifact/'outputs';output.mkdir(parents=True)
        self.answer=output/'answer.json';self.answer.write_text('{"total": 42}')
        self.stopped=[{'role':'assistant','content':'Artifact saved.'}]

    def grade(self,messages=None,artifacts=None,**kwargs):
        return grade_workflow(self.stopped if messages is None else messages,self.root,
                              [self.artifact] if artifacts is None else artifacts,{'total':42},**kwargs)

    def test_correct_artifact_and_stop(self):
        result=self.grade()
        self.assertTrue(result['artifact_pass']);self.assertTrue(result['latest_artifact_pass'])
        self.assertTrue(result['stopped_with_correct_artifact'])
        self.assertTrue(result['stopped_with_correct_latest_artifact'])
        self.assertEqual(result['termination'],'agent_stop')

    def test_correct_artifact_at_turn_limit_is_not_finished(self):
        messages=[]
        for _ in range(12):
            messages.extend([{'role':'assistant','tool_calls':[{'id':'call'}]},
                             {'role':'tool','content':'Content withheld.'}])
        result=self.grade(messages)
        self.assertTrue(result['artifact_pass']);self.assertEqual(result['termination'],'turn_limit')
        self.assertFalse(result['stopped_with_correct_artifact'])

    def test_last_turn_stop_is_a_stop(self):
        messages=[{'role':'assistant','tool_calls':[{'id':'call'}]} for _ in range(11)]+self.stopped
        self.assertEqual(self.grade(messages)['termination'],'agent_stop')

    def test_earlier_correct_artifact_does_not_mask_latest_failure(self):
        latest='b'*32;output=self.root/latest/'outputs';output.mkdir(parents=True)
        (output/'answer.json').write_text('{"total": 0}')
        result=self.grade(artifacts=[self.artifact,latest])
        self.assertTrue(result['artifact_pass']);self.assertFalse(result['latest_artifact_pass'])
        self.assertTrue(result['stopped_with_correct_artifact'])
        self.assertFalse(result['stopped_with_correct_latest_artifact'])

    def test_stop_without_artifact_is_not_success(self):
        result=self.grade(artifacts=[])
        self.assertTrue(result['agent_stopped']);self.assertFalse(result['stopped_with_correct_artifact'])

    def test_scripted_and_error_runs_do_not_count_as_agent_stops(self):
        for kwargs,termination in [({'scripted':True},'scripted'),({'error':'ValueError'},'controller_error'),
                                   ({'messages':[]},'incomplete')]:
            with self.subTest(termination=termination):
                result=self.grade(**kwargs)
                self.assertTrue(result['artifact_pass']);self.assertEqual(result['termination'],termination)
                self.assertFalse(result['stopped_with_correct_artifact'])

    def test_untrusted_artifact_paths_are_rejected(self):
        for artifact in ['../escape','a'*32+'/../escape',None,'unknown']:
            with self.subTest(artifact=artifact):self.assertFalse(self.grade(artifacts=[artifact])['artifact_pass'])

    def test_answer_symlink_and_parent_symlink_are_rejected(self):
        self.answer.unlink();target=self.root/'outside.json';target.write_text('{"total": 42}')
        self.answer.symlink_to(target)
        self.assertFalse(self.grade()['artifact_pass'])
        self.answer.unlink();self.answer.parent.rmdir()
        outside=self.root/'outside';outside.mkdir();(outside/'answer.json').write_text('{"total": 42}')
        self.answer.parent.symlink_to(outside,target_is_directory=True)
        self.assertFalse(self.grade()['artifact_pass'])

    def test_malformed_or_oversized_artifact_is_rejected(self):
        for content in ['not json','{"total": 42}'+(' '*65_537),'{"total": 0}','['*5000+']'*5000]:
            self.answer.write_text(content)
            self.assertFalse(self.grade()['artifact_pass'])


if __name__=='__main__':unittest.main()
