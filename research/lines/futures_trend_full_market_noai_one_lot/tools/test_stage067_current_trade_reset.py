"""Append-only Reset axes fix: public Plotly API, current trade and no data edits."""
import hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).parent;ENTRY=HERE/'stage067_current_trade_reset.py';NODE='/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'

class CurrentTradeResetTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.exists(),'current-trade Reset axes adapter missing')
        spec=importlib.util.spec_from_file_location('stage067_fixture',ENTRY);self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)

    def test_node_fake_dom_reset_uses_current_trade_and_visible_periods_only(self):
        harness=r'''
const vm=require('vm'),assert=require('assert'),fs=require('fs');const script=JSON.parse(fs.readFileSync(0,'utf8'));let listener,capture,calls=[];
const button={inside:true},outside={inside:false};const chart={contains:b=>b.inside};
Object.defineProperty(chart,'_fullLayout',{get(){throw Error('private state read')}});
const document={getElementById:id=>id==='chart'?chart:null,addEventListener:(name,fn,cap)=>{assert.equal(name,'click');listener=fn;capture=cap}};
const context=vm.createContext({document,Plotly:{relayout:(chartArg,update)=>{assert.equal(chartArg,chart);calls.push(JSON.parse(JSON.stringify(update)))}}});
vm.runInContext("let filtered=[{meta:{chart_x_start:0,chart_x_end:315}},{meta:{chart_x_start:1145,chart_x_end:1658}}];let active=0;let visibleCount=2;function visiblePeriodOptions(meta){return Array.from({length:visibleCount},(_,i)=>({id:String(i)}))}",context);
vm.runInContext(script,context);assert.strictEqual(capture,true);
function event(b){return {target:{closest:selector=>b},prevented:0,stopped:0,preventDefault(){this.prevented++},stopImmediatePropagation(){this.stopped++}}}
let e=event(button);listener(e);assert.equal(e.prevented,1);assert.equal(e.stopped,1);assert.deepStrictEqual(calls[0]['xaxis.range'],[0,315]);assert.deepStrictEqual(calls[0]['xaxis2.range'],[0,315]);assert.equal(calls[0]['xaxis.autorange'],false);assert.equal(calls[0]['yaxis4.autorange'],true);assert.equal(Object.keys(calls[0]).length,8);
vm.runInContext('active=1;visibleCount=3',context);e=event(button);listener(e);let update=calls[1];assert.deepStrictEqual(update['xaxis.range'],[1145,1658]);assert.deepStrictEqual(update['xaxis3.range'],[1145,1658]);assert.equal(update['xaxis3.autorange'],false);assert.equal(update['yaxis6.autorange'],true);assert.equal(Object.keys(update).length,12);
for(const b of [outside,null]){e=event(b);listener(e);assert.equal(e.prevented,0);assert.equal(e.stopped,0)}
vm.runInContext('filtered=[]',context);e=event(button);listener(e);assert.equal(e.prevented,0);assert.equal(calls.length,2);
vm.runInContext('filtered=[{meta:{chart_x_start:0,chart_x_end:315}}];active=0;visibleCount=0',context);e=event(button);listener(e);assert.equal(e.prevented,0);assert.equal(calls.length,2);
console.log('PASS two trades, 2 to 3 periods, empty, other buttons and public API');
'''
        result=subprocess.run([NODE,'-e',harness],input=json.dumps(self.mod.SCRIPT),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PASS two trades',result.stdout)

    def fixture(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);parent=root/'reviewed';parent.mkdir()
        records=[dict(meta=dict(vt_symbol='ag202602.SHFE',chart_x_start=1145,chart_x_end=1658),weekly=dict(close=[100,101],ma40=[None,None]))]
        (parent/'records.json').write_text(json.dumps(records));(parent/'chart_manifest.csv').write_text('vt_symbol\nag202602.SHFE\n')
        (parent/'index.html').write_text('<html><body><div id="chart"></div><script>const records='+json.dumps(records)+';let filtered=records;let active=0;function visiblePeriodOptions(meta){return []}</script></body></html>')
        (parent/'weekly_contract_chart_features.csv').write_text('unchanged financial/plot evidence\n')
        summary=dict(backtest_metrics=dict(end_balance=1205102.8112954884,total_return=20.510281129548847),source_manifest_sha256='f'*64,source_warning='frozen disclosure',weekly_contract_enrichment={'unchanged':True})
        summary['artifact_sha256']={p.name:self.mod.sha(p) for p in parent.iterdir()};(parent/'summary.json').write_text(json.dumps(summary));return root,parent,summary

    def test_append_only_html_all_old_artifacts_and_frozen_summary_preserved(self):
        root,parent,before=self.fixture();out=root/'reviewed_v2';original=(parent/'index.html').read_bytes();r=self.mod.generate(parent,out)
        page=(out/'index.html').read_bytes();addition=self.mod.script_tag().encode();self.assertEqual(page.replace(addition,b'',1),original)
        self.assertEqual(r['backtest_metrics'],before['backtest_metrics']);self.assertEqual(r['source_warning'],before['source_warning']);self.assertEqual(r['weekly_contract_enrichment'],before['weekly_contract_enrichment'])
        for name in before['artifact_sha256']:
            if name!='index.html':self.assertEqual((out/name).read_bytes(),(parent/name).read_bytes())
        for name,digest in r['artifact_sha256'].items():self.assertEqual(self.mod.sha(out/name),digest)
        self.assertTrue(r['ui_reset_fix']['embedded_records_identical']);self.assertTrue(r['ui_reset_fix']['other_artifacts_byte_identical'])
        self.assertEqual((parent/'index.html').read_bytes(),original)
        with self.assertRaises(FileExistsError):self.mod.generate(parent,out)

    def test_tamper_nesting_and_repeated_patch_rejected(self):
        root,parent,before=self.fixture()
        with self.assertRaises(ValueError):self.mod.generate(parent,parent/'child')
        (parent/'records.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'parent_hash'):self.mod.generate(parent,root/'bad')
        self.assertFalse((root/'bad').exists())
        with self.assertRaisesRegex(ValueError,'already_patched'):self.mod.patch_html('<body>'+self.mod.script_tag()+'</body>')

if __name__=='__main__':unittest.main()
