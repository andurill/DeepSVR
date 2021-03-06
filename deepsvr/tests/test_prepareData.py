from unittest import TestCase
from deepsvr.PrepareData import PrepareData
import os

TEST_DATA_BASE_DIR = './deepsvr/tests/test_data'


def file_len(fname):
    """Source: https://stackoverflow.com/q/845058/3862525"""
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1


class TestPrepareData(TestCase):
    @classmethod
    def setUpClass(cls):
        # Test processing sample file w/o header
        cls.samples_noheader = PrepareData(os.path.join(TEST_DATA_BASE_DIR,
                                                        'samples.noheader.tsv'
                                                        ),
                                           False,
                                           os.path.join(TEST_DATA_BASE_DIR,
                                                        'training_data'),
                                           False, True)
        # process sample file with header
        cls.samples_header = PrepareData(os.path.join(TEST_DATA_BASE_DIR,
                                                      'samples.tsv'),
                                         True,
                                         os.path.join(TEST_DATA_BASE_DIR,
                                                      'training_data'), True,
                                         True)
        # Test when no reviewer is specified
        cls.no_reviewer = PrepareData(os.path.join(TEST_DATA_BASE_DIR,
                                                   'samples_no_reviewer.tsv'),
                                      True,
                                      os.path.join(TEST_DATA_BASE_DIR,
                                                   'training_data',
                                                   'no_reviewer'), False,
                                      False)
        # Test overiding the reviewer when specified in the sample file but not
        # in the review file
        cls.sample_reviewer = PrepareData(os.path.join
                                          (TEST_DATA_BASE_DIR,
                                           'samples_with_reviewer.tsv'),
                                          True,
                                          os.path.join(TEST_DATA_BASE_DIR,
                                                       'training_data',
                                                       'reviewer_in_sample'),
                                          False,
                                          True)

    def test__parse_samples_file(self):
        self.assertTrue(len(self.samples_header.samples) == 1)
        self.assertTrue(len(self.samples_noheader.samples) == 1)

    def test__run_bam_readcount(self):
        # bam-readcount files counted 443 variants
        self.assertEqual(file_len(os.path.join(TEST_DATA_BASE_DIR,
                                               'training_data', 'readcounts',
                                               'tst1_normal.readcounts')),
                         10)
        self.assertEqual(file_len(os.path.join(TEST_DATA_BASE_DIR,
                                               'training_data', 'readcounts',
                                               'tst1_tumor.readcounts')),
                         10)
        # all variants are successfully parsed from the readcount files
        self.assertEqual(len(self.samples_noheader.training_data), 10)
        # training data has the expected number of feature columns
        self.assertEqual(len(self.samples_noheader.training_data.columns), 59)
        self.assertEqual(
            round(self.samples_noheader.training_data.values.max(), 3), 1)
        # all variants are successfully parsed from the readcount files
        self.assertEqual(len(self.no_reviewer.training_data), 10)
        # training data has the expected number of feature columns
        self.assertEqual(len(self.no_reviewer.training_data.columns), 59)
        # all variants are successfully parsed from the readcount files
        self.assertEqual(len(self.sample_reviewer.training_data), 10)
        # training data has the expected number of feature columns
        self.assertEqual(len(self.sample_reviewer.training_data.columns), 59)
