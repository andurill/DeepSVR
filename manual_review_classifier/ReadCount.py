import re
import pandas as pd
import copy
from manual_review_classifier.utils import to_numeric

BASE_METRICS = ['count', 'avg_mapping_quality', 'avg_basequality',
                'avg_se_mapping_quality', 'num_plus_strand',
                'num_minus_strand', 'avg_pos_as_fraction',
                'avg_num_mismaches_as_fraction', 'avg_sum_mismatch_qualities',
                'num_q2_containing_reads',
                'avg_distance_to_q2_start_in_q2_reads',
                'avg_clipped_length', 'avg_distance_to_effective_3p_end']


class ReadCount:
    """Parse bam-readcount out into dict or pandas.Dataframe
    
    """

    def __init__(self, file_path):
        """Initialize dict of bam-readcount file.
        
        Args:
            file_path (str): File path of bam-readcount file  
        """
        self.read_count_dict = self._parse(file_path)
        self.read_count_df = pd.DataFrame()

    def _parse(self, file_path):
        """Read and parse the bam_readcount file into a dict
        
        Args:
            file_path (str): File path of bam-readcount file  
        
        Returns:
            dict of bam-readcount
        """
        file = open(file_path)
        counts = {}
        for line in file:
            match = re.match(r'(^[\w|.]+\t\d+\t\w\t\d+)', line)
            if match is not None:
                count = re.split('\t|:', line.strip())
                position = '{0}:{1}'.format(count[0], count[1])
                metrics = {}
                metrics['chromosome'] = count[0]
                metrics['position'] = int(count[1])
                metrics['ref'] = count[2]
                metrics['depth'] = int(count[3])
                bases = {}
                for i in range(4, len(count), 14):
                    b = list(map(to_numeric, count[i + 1: i + 14]))
                    # if not all(x == 0 for x in b):
                    if count[i] != '=':
                        bases[count[i]] = dict(zip(BASE_METRICS, b))
                metrics['bases'] = bases
                counts[position] = metrics
        return counts

    def compute_variant_metrics(self, var_bed_file_path,
                                sample_prepend_string):
        """
        
        Args:
            var_bed_file_path (str): filepath to bed file indicating variants
        
        Returns:
             pandas.Dataframe of variant centric read count data 
        """
        self.bam_readcount_keys = list(self.read_count_dict.keys())
        if len(self.read_count_df) > 0:
            return self.read_count_df
        with open(var_bed_file_path, 'r') as f:
            for line in f:
                debug = line.strip()
                line = line.strip().split('\t')
                chromosome, start, stop, reference, variant, call = line
                start = int(start)
                stop = int(stop)
                bam_readcount_site = '{0}:{1}'.format(chromosome, start)
                variant_site = '{0}:{1}{2}>{3}'.format(chromosome, start, reference,
                                               variant)
                # insertions
                if reference == '-':
                    try:
                        self.flatten_base_metrics(
                            self.read_count_dict[bam_readcount_site]['ref'], bam_readcount_site, variant_site,
                            sample_prepend_string + '_ref')
                    except KeyError:
                        # bamreadcout does not output metrics for zero depth sites
                        self._add_zero_depth_readcount_to_dict(reference, bam_readcount_site, variant_site, sample_prepend_string + '_ref')
                    self.flatten_base_metrics('+{0}'.format(variant), bam_readcount_site, variant_site,
                                              sample_prepend_string + '_var')
                # deletions
                elif variant == '-':
                    try:
                        self.flatten_base_metrics(
                            self.read_count_dict[bam_readcount_site]['ref'], bam_readcount_site, variant_site,
                            sample_prepend_string + '_ref')
                    except KeyError:
                        self._add_zero_depth_readcount_to_dict(reference, bam_readcount_site, variant_site,
                                                  sample_prepend_string + '_ref')
                    self.flatten_base_metrics('-{0}'.format(reference), bam_readcount_site, variant_site,
                                              sample_prepend_string + '_var')
                # snvs
                else:
                    self.flatten_base_metrics(reference, bam_readcount_site, variant_site,
                                              sample_prepend_string + '_ref')
                    self.flatten_base_metrics(variant, bam_readcount_site, variant_site,
                                              sample_prepend_string + '_var')
                other_bases_count = 0
                try:
                    for base in self.read_count_dict[bam_readcount_site]['bases']:
                        # TODO check if other base metrics are nearly identical due to proximity
                        if base not in self.read_count_dict[bam_readcount_site]['seen_base']:
                            other_bases_count += \
                                self.read_count_dict[bam_readcount_site]['bases'][base]['count']
                    self.read_count_dict[bam_readcount_site].pop('seen_base')
                except KeyError:
                    print(chromosome, start, stop, reference, variant)
                    print(self.read_count_dict[bam_readcount_site])
                    raise KeyError
                self.read_count_dict[variant_site][
                    sample_prepend_string + '_other_bases_count'] = other_bases_count
                # self.read_count_dict[bam_readcount_site].pop('bases')
                self.read_count_dict[variant_site]['chromosome'] = chromosome
                self.read_count_dict[variant_site]['ref'] = reference
                self.read_count_dict[variant_site]['var'] = variant
                self.read_count_dict[variant_site]['call'] = call
                self.read_count_dict[variant_site]['stop'] = stop
                self.read_count_dict[variant_site]['start'] = self.read_count_dict[
                    bam_readcount_site]['position']
                self.read_count_dict[variant_site][sample_prepend_string + '_depth'] = \
                self.read_count_dict[bam_readcount_site]['depth']
        # This will delete all the bam-readcount keys including count of other positions from indels
        # This dropping the counts at other positions could eliminate some real signal
        for key in self.bam_readcount_keys:
            self.read_count_dict.pop(key)
        self.read_count_df = pd.DataFrame.from_dict(self.read_count_dict,
                                                    orient='index')
        self.read_count_df[sample_prepend_string + '_VAF'] = \
        self.read_count_df[sample_prepend_string + '_var_count'] / \
        self.read_count_df[sample_prepend_string + '_depth']
        return self.read_count_df

    def remove_extra_indel_counts(self, chromosome, start, stop):
        for i in range(start + 1, stop + 1):
            remove_site = '{0}:{1}'.format(chromosome, i)
            self.read_count_dict.pop(remove_site)

    def flatten_base_metrics(self, base_key, bam_readcount_site, variant_site, prepend_string):
        """ Renames the base metrics and flatten the data into the site level
        
        :param base_key (str): Key for the reference or variant 
        :param site (str): Site string 
        :param prepend_string (str): string to prepend the new keys
        """

        try:
            # Remove ref or var metrics so counts for other bases can be summed
            self.read_count_dict[bam_readcount_site].setdefault('seen_base',
                                                                []).append(
                                                                    base_key)
            for metric_key in self.read_count_dict[bam_readcount_site]['bases'][base_key]:
                new_key = '{0}_{1}'.format(prepend_string, metric_key)
                self.read_count_dict.setdefault(variant_site, {})
                self.read_count_dict[variant_site][new_key] = \
                    self.read_count_dict[bam_readcount_site]['bases'][base_key][metric_key]

        except KeyError:
            # bam-readcount does not output zero depth sites, this adds them to the dictionary assuming that the keyError was raised on the ref call
            if bam_readcount_site not in self.read_count_dict:
                self._add_zero_depth_readcount_to_dict(base_key,
                                                       bam_readcount_site,
                                                       variant_site,
                                                       prepend_string)
            else:
            # add all zero metrics for indels absent from count file
                keys = ['{0}_{1}'.format(prepend_string, i) for i in BASE_METRICS]
                # self.read_count_dict[variant_site]= copy.deepcopy(self.read_count_dict[bam_readcount_site])
                # self.read_count_dict[variant_site].pop('bases')
                self.read_count_dict.setdefault(variant_site, {}).update(dict.fromkeys(keys, 0))



    def _add_zero_depth_readcount_to_dict(self, base_key, bam_readcount_site, variant_site, prepend_string ):
        variant_site_search = re.search('(\w+):(\d+)[\w|-]+>[\w|-]+', variant_site)
        chromosome = variant_site_search.group(1)
        position = variant_site_search.group(2)
        self.bam_readcount_keys.append(bam_readcount_site)
        self.read_count_dict[bam_readcount_site] = {
                        'bases': {'A': {'avg_basequality': 0.0,
                                        'avg_clipped_length': 0.0,
                                        'avg_distance_to_effective_3p_end': 0.0,
                                        'avg_distance_to_q2_start_in_q2_reads': 0.0,
                                        'avg_mapping_quality': 0.0,
                                        'avg_num_mismaches_as_fraction': 0.0,
                                        'avg_pos_as_fraction': 0.0,
                                        'avg_se_mapping_quality': 0.0,
                                        'avg_sum_mismatch_qualities': 0.0,
                                        'count': 0,
                                        'num_minus_strand': 0,
                                        'num_plus_strand': 0,
                                        'num_q2_containing_reads': 0},
                                  'C': {'avg_basequality': 0.0,
                                        'avg_clipped_length': 0.0,
                                        'avg_distance_to_effective_3p_end': 0.0,
                                        'avg_distance_to_q2_start_in_q2_reads': 0.0,
                                        'avg_mapping_quality': 0.0,
                                        'avg_num_mismaches_as_fraction': 0.0,
                                        'avg_pos_as_fraction': 0.0,
                                        'avg_se_mapping_quality': 0.0,
                                        'avg_sum_mismatch_qualities': 0.0,
                                        'count': 0,
                                        'num_minus_strand': 0,
                                        'num_plus_strand': 0,
                                        'num_q2_containing_reads': 0},
                                  'G': {'avg_basequality': 0.0,
                                        'avg_clipped_length': 0.0,
                                        'avg_distance_to_effective_3p_end': 0.0,
                                        'avg_distance_to_q2_start_in_q2_reads': 0.0,
                                        'avg_mapping_quality': 0.0,
                                        'avg_num_mismaches_as_fraction': 0.0,
                                        'avg_pos_as_fraction': 0.0,
                                        'avg_se_mapping_quality': 0.0,
                                        'avg_sum_mismatch_qualities': 0.0,
                                        'count': 0,
                                        'num_minus_strand': 0,
                                        'num_plus_strand': 0,
                                        'num_q2_containing_reads': 0},
                                  'N': {'avg_basequality': 0.0,
                                        'avg_clipped_length': 0.0,
                                        'avg_distance_to_effective_3p_end': 0.0,
                                        'avg_distance_to_q2_start_in_q2_reads': 0.0,
                                        'avg_mapping_quality': 0.0,
                                        'avg_num_mismaches_as_fraction': 0.0,
                                        'avg_pos_as_fraction': 0.0,
                                        'avg_se_mapping_quality': 0.0,
                                        'avg_sum_mismatch_qualities': 0.0,
                                        'count': 0,
                                        'num_minus_strand': 0,
                                        'num_plus_strand': 0,
                                        'num_q2_containing_reads': 0},
                                  'T': {'avg_basequality': 0.0,
                                        'avg_clipped_length': 0.0,
                                        'avg_distance_to_effective_3p_end': 0.0,
                                        'avg_distance_to_q2_start_in_q2_reads': 0.0,
                                        'avg_mapping_quality': 0.0,
                                        'avg_num_mismaches_as_fraction': 0.0,
                                        'avg_pos_as_fraction': 0.0,
                                        'avg_se_mapping_quality': 0.0,
                                        'avg_sum_mismatch_qualities': 0.0,
                                        'count': 0,
                                        'num_minus_strand': 0,
                                        'num_plus_strand': 0,
                                        'num_q2_containing_reads': 0}},
                        'chromosome': chromosome,
                        'depth': 0,
                        'position': position,
                        'ref': base_key}
        self.flatten_base_metrics(base_key, bam_readcount_site, variant_site, prepend_string)