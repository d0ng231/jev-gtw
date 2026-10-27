import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from jev_gtw.sandbox import ProbeRunner


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_docker_requires_pinned_image(self):
        with self.assertRaises(ValueError):ProbeRunner(backend='docker',image='python:latest',artifact_root=self.root,executable='/usr/bin/docker')

    def test_docker_isolated_arguments(self):
        runner=ProbeRunner(backend='docker',image='python@sha256:'+'a'*64,artifact_root=self.root,executable='/usr/bin/docker')
        args=runner.argv(self.root/'job','test-container')
        for flag in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32']:
            self.assertIn(flag,args)
        self.assertFalse(any('docker.sock' in arg for arg in args))
        self.assertTrue(any('target=/inputs,readonly' in arg for arg in args))

    def test_sif_content_hash_is_checked(self):
        path=self.root/'fake.sif';path.write_bytes(b'fake')
        with self.assertRaises(ValueError):ProbeRunner(backend='apptainer',image=str(path),image_sha256='0'*64,artifact_root=self.root,executable='/usr/bin/apptainer')
        runner=ProbeRunner(backend='apptainer',image=str(path),image_sha256=hashlib.sha256(b'fake').hexdigest(),artifact_root=self.root,executable='/usr/bin/apptainer')
        args=runner.argv(self.root/'job','name')
        for flag in ['--containall','--cleanenv','--no-home','--net','none']:self.assertIn(flag,args)

    def test_public_artifact_directory_rejected(self):
        path=self.root/'public';path.mkdir(mode=0o755)
        with self.assertRaises(ValueError):ProbeRunner(backend='docker',image='python@sha256:'+'a'*64,artifact_root=path,executable='/usr/bin/docker')


if __name__=='__main__':unittest.main()
