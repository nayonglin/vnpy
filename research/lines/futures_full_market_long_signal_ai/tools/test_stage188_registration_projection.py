"""Finite synthetic source/identity contracts only; no accepted arrays or raw."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parent


def load():
    p=TOOLS/'stage188_registration_projection.py'
    if not p.exists():return None
    s=importlib.util.spec_from_file_location('fixture188',p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


class RegistrationProjection(unittest.TestCase):
    def setUp(self):
        self.m=load();self.assertIsNotNone(self.m,'Stage188 implementation missing')
        self.dates=[f'2020-01-{i:02d}' for i in range(1,9)]

    def scope(self,date,scope_id='g',quantity='1',*,product='P.X',coverage='leafA',version='R0',state='conditional_source_qualified'):
        return dict(request_date=date,scope_id=scope_id,mapped_research_product_id=product,mapping_state='exact_overlay',
            required=True,status=state,reasons=[],quantity_value=quantity,official_delta_value='999999',
            ordinary_total_count=1,leaf_coverage_fingerprint=coverage,coverage_state='complete_nonduplicated_source_rows',
            scope_identity=dict(source_format='json',representation_version=version,raw_VARNAME='raw '+scope_id,
                raw_WGHTUNIT='CODE1',VARID_presence='field_absent',raw_VARID=None,
                WHTYPE_presence='field_absent',raw_WHTYPE=None))

    def status(self,date,ids=('g',),*,product='P.X',state='conditional_all_required_scopes_qualified',complete=True,bad=(),unresolved=()):
        return dict(request_date=date,mapped_research_product_id=product,required_scope_ids=list(ids),bad_scope_ids=list(bad),
            scope_membership_complete=complete,status=state,unresolved_report_scope_ids=list(unresolved),reasons=[])

    def source(self,scopes=None,statuses=None):
        return self.m.RegistrationSource(scopes or [self.scope(self.dates[1],quantity='1'),self.scope(self.dates[2],quantity='3')],
            statuses or [self.status(self.dates[1]),self.status(self.dates[2])],self.dates)

    def test_ratio_is_scale_invariant_signed_and_double_known_zero_distinct_from_missing(self):
        self.assertEqual(self.m.scope_ratio('3','1'),self.m.scope_ratio('3000','1000'))
        self.assertEqual(self.m.scope_ratio('3','1'),-self.m.scope_ratio('1','3'))
        self.assertEqual(self.m.scope_ratio('0','0'),0)
        with self.assertRaises(ValueError):self.m.scope_ratio('','0')
        with self.assertRaises(ValueError):self.m.scope_ratio('-1','2')
        with self.assertRaises(ValueError):self.m.scope_ratio('NaN','2')

    def test_mean_is_over_complete_scope_ratios_not_quantities_or_official_delta(self):
        rows=[self.scope(self.dates[1],'g','1'),self.scope(self.dates[2],'g','3'),
            self.scope(self.dates[1],'h','30000'),self.scope(self.dates[2],'h','10000')]
        source=self.source(rows,[self.status(d,('g','h')) for d in self.dates[1:3]])
        result=source.at_decision('P.X',3,self.dates[3])
        self.assertEqual(result['scalar_primary'],'0');self.assertEqual(result['scalar_missing'],0)
        self.assertEqual(result['scope_count'],2)

    def test_any_bad_required_scope_or_unresolved_membership_blocks_whole_product(self):
        for invalid in ('bad','unresolved','incomplete','missing_scope'):
            rows=[self.scope(self.dates[1]),self.scope(self.dates[2],quantity='3')]
            statuses=[self.status(self.dates[1]),self.status(self.dates[2])]
            if invalid=='bad':statuses[1].update(status='unknown',bad_scope_ids=['g'])
            elif invalid=='unresolved':statuses[1]['unresolved_report_scope_ids']=['unknownRaw']
            elif invalid=='incomplete':statuses[1]['scope_membership_complete']=False
            else:statuses[1]['required_scope_ids']=['g','absent']
            result=self.source(rows,statuses).at_decision('P.X',3,self.dates[3])
            self.assertEqual(result['scalar_missing'],1,invalid);self.assertEqual(result['scalar_primary'],'')

    def test_scope_coverage_schema_and_presence_breaks_never_form_a_pair(self):
        for changed in ('scope','coverage','coverage_state','schema','presence'):
            rows=[self.scope(self.dates[1]),self.scope(self.dates[2],quantity='3')]
            statuses=[self.status(self.dates[1]),self.status(self.dates[2])]
            if changed=='scope':rows[1]['scope_id']='new';statuses[1]['required_scope_ids']=['new']
            elif changed=='coverage':rows[1]['leaf_coverage_fingerprint']='leafB'
            elif changed=='coverage_state':rows[1]['coverage_state']='unknown'
            elif changed=='schema':rows[1]['scope_identity']['representation_version']='R1'
            else:rows[1]['scope_identity']['VARID_presence']='field_present_literal_value';rows[1]['scope_identity']['raw_VARID']='X'
            self.assertEqual(self.source(rows,statuses).at_decision('P.X',3,self.dates[3])['scalar_missing'],1,changed)

    def test_clock_uses_original_decision_minus1_minus2_and_never_nearest_or_fill(self):
        source=self.source();r=source.at_decision('P.X',3,self.dates[3])
        self.assertEqual((r['decision_date'],r['prospective_entry_date'],r['report_v'],r['report_w']),
            (self.dates[3],self.dates[4],self.dates[2],self.dates[1]))
        self.assertEqual(r['scalar_primary'],'0.5')
        self.assertEqual((r['report_v_index'],r['report_w_index']),(2,1))
        prefixed=self.m.RegistrationSource([self.scope(self.dates[1]),self.scope(self.dates[2],quantity='3')],
            [self.status(self.dates[1]),self.status(self.dates[2])],['2005-01-04']+self.dates)
        p=prefixed.at_decision('P.X',4,self.dates[3])
        self.assertEqual((p['report_v_index'],p['report_w_index'],p['prospective_entry_index']),(3,2,5))
        self.assertEqual(source.at_decision('P.X',4,self.dates[4])['scalar_missing'],1)
        self.assertEqual(source.at_decision('P.X',0,self.dates[0])['scalar_missing'],1)
        with self.assertRaises(ValueError):source.at_decision('P.X',3,self.dates[4])

    def identities(self):
        mothers=[dict(sequence_index='0',event_id='m0',product_id='P.X',family_id='P.X',u_date=self.dates[3],u_index='3',reference_epoch='P.X.202012'),
            dict(sequence_index='1',event_id='m1',product_id='P.X_F',family_id='P.X',u_date=self.dates[3],u_index='3',reference_epoch='P.X_F.202012')]
        actions=[dict(action_id='a'+str(i),event_id='a'+str(i),action_sequence_index=str(i),mother_sequence_index=str(parent),
            mother_event_id=mothers[parent]['event_id'],product_id=mothers[parent]['product_id'],family_id='P.X',
            u_date=self.dates[3],u_index='3',reference_epoch='child'+str(i),anchor_epoch=mothers[parent]['reference_epoch'])
            for i,parent in enumerate((0,0,1))]
        return mothers,actions

    def test_all_original_identities_children_and_unmapped_F_are_preserved_without_alias(self):
        mothers,actions=self.identities()
        with tempfile.TemporaryDirectory() as directory:
            receipt=self.m.project_identity_records(Path(directory),iter(mothers),iter(actions),self.source(),
                expected=dict(mothers=2,actions=3,products=2,families=1,exchanges=1,forward_parents=2),fixture=True)
            mp=self.m.read_csv_records(Path(directory)/'mothers_projection.csv.gz')
            ap=self.m.read_csv_records(Path(directory)/'actions_projection.csv.gz')
            self.assertEqual([r['action_id'] for r in ap],[r['action_id'] for r in actions])
            self.assertEqual([r['event_id'] for r in mp],['m0','m1'])
            self.assertEqual([r['scalar_primary'] for r in ap],['0.5','0.5',''])
            self.assertEqual(ap[2]['feature_state'],'unknown_no_product_status')
            self.assertEqual(receipt['old_source_label_columns_read'],[])
            self.assertEqual(receipt['actions'],3)
            coverage=self.m.read_csv_records(Path(directory)/'coverage_by_product_year.csv.gz')
            self.assertTrue(all(r['known_zero']=='0' for r in coverage))

    def test_duplicate_source_or_invalid_parent_action_closure_is_rejected(self):
        with self.assertRaises(ValueError):self.source([self.scope(self.dates[1]),self.scope(self.dates[1])])
        mothers,actions=self.identities();actions[1]['mother_event_id']='wrong'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'parent'):
                self.m.project_identity_records(Path(directory),iter(mothers),iter(actions),self.source(),
                    expected=dict(mothers=2,actions=3,products=2,families=1,exchanges=1,forward_parents=2),fixture=True)

    def test_explicit_not_applicable_is_retained_and_source_size_guard_no_big_hash(self):
        statuses=[self.status(d,(),product='FIN.X',state='not_applicable') for d in self.dates[1:3]]
        r=self.source([self.scope(self.dates[1])],statuses).at_decision('FIN.X',3,self.dates[3])
        self.assertEqual(r['feature_state'],'not_applicable');self.assertEqual(r['scalar_missing'],1)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'source.gz';p.write_bytes(b'fake-data')
            binding=dict(path=str(p),bytes=9,sha256='inherited-not-rehashed')
            before=self.m.source_stat(binding)
            self.assertEqual(before['sha256_check'],'inherited_acceptance_not_rehashed')
            p.write_bytes(b'changed-data')
            with self.assertRaises(ValueError):self.m.source_stat(binding)

    def test_187_must_accept_and_bind_exact_same_completed186_before_any_data_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            def save(name,value):
                p=folder/name;p.write_text(json.dumps(value),encoding='utf-8');return self.m.file_binding(p)
            inherited={role:dict(path=str(folder/(role+'.not-read')),bytes=123,sha256='inherited')
                for role in ('scope_observations','product_scope_status','mothers','actions','calendar')}
            inherited['product_overlay']=save('overlay.json',{})
            inherited['dataset_manifest']=save('dataset.json',dict(schema='stage129_contract_choice_dataset_v1',
                status='completed',mother_rows=399252,action_rows=1552456,
                mothers=inherited['mothers'],actions=inherited['actions']))
            terminal=save('terminal.json',dict(status='completed',exit_code=0))
            inherited['normalization_manifest']=save('norm.json',dict(
                schema='stage186_warehouse_history_normalization_manifest_v1',status='completed',terminal=terminal,
                scope_observations=inherited['scope_observations'],product_scope_status=inherited['product_scope_status'],
                product_overlay=inherited['product_overlay'],calender=inherited['calendar']))
            review=dict(schema='stage187_registration_normalization_review_v1',accepted=False,C=0,I=0,M=0,
                normalization_manifest=inherited['normalization_manifest'])
            inherited['normalization_review']=save('review1.json',review)
            with self.assertRaisesRegex(ValueError,'accepted187'):self.m.validate_metadata(inherited)
            review['accepted']=True;review['normalization_manifest']=dict(inherited['normalization_manifest'],sha256='wrong')
            inherited['normalization_review']=save('review2.json',review)
            with self.assertRaisesRegex(ValueError,'187 same186'):self.m.validate_metadata(inherited)
            review['normalization_manifest']=inherited['normalization_manifest']
            inherited['normalization_review']=save('review3.json',review)
            norm,accepted,_=self.m.validate_metadata(inherited)
            self.assertTrue(accepted['accepted']);self.assertEqual(norm['status'],'completed')
            # validate_metadata never opened any .not-read array/raw/identity stream.
            self.assertFalse(any(folder.glob('*.not-read')))


if __name__=='__main__':unittest.main()
