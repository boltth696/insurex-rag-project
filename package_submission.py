"""Build a reviewed source submission without credentials or customer databases."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def submission_files():
    names = ['README.md','requirements.txt','requirements.lock.txt','.env.example','.gitignore',
             'app.py','Start Chatbot.cmd','New Chatbot Instance.cmd','Stop Chatbot.cmd','Start-Chatbot.ps1',
             '.streamlit/config.toml']
    files = [ROOT/name for name in names]
    files += sorted((ROOT/'insurex').glob('*.py'))
    files += sorted((ROOT/'tests').glob('*.py'))
    files += sorted((ROOT/'data').glob('*.json'))
    catalog = json.loads((ROOT/'data/product_catalog.json').read_text(encoding='utf-8'))
    expected_sources = {}
    for product in catalog['products']:
        name = product['source_file']
        if Path(name).name != name:
            raise ValueError('Brochure source must be a plain filename.')
        source = ROOT/'data/pdfs'/name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != product['source_sha256']:
            raise ValueError('Brochure does not match the reviewed catalog.')
        expected_sources[name] = digest
        files.append(source)
    index_dir = ROOT/'storage/faiss'
    manifest_path = index_dir/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    indexed_sources = {row['file']:row['sha256'] for row in manifest['files']}
    if indexed_sources != expected_sources:
        raise ValueError('FAISS manifest does not match reviewed brochures.')
    files.append(manifest_path)
    for key in ('index_file','documents_file'):
        name = manifest[key]
        if Path(name).name != name:
            raise ValueError('Invalid index filename.')
        files.append(index_dir/name)
    demo_names = ['DEMO_TEST_CASE_LOG.md','submission-demo.md','submission-demo.json',
                  'submission-demo-before-fix.json','submission-demo-checker-original.json','submission-manual-review.json',
                  'offline-demo.md','offline-demo.json','release-validation.json',
                  'run_submission_demo.py','package_submission.py','workflow.md','lead-collection-guide.md',
                  'variation-review.md','final-test-summary.json','launcher-checks.json',
                  'saved-information-checks.json','evaluate_variations.py','variation_cases.json',
                  'customer_examples.json','factual_cases.json','stress_cases.json','frequency_cases.json',
                  'payment_wording_cases.json','entry_age_cases.json']
    summary = json.loads((ROOT/'demo/final-test-summary.json').read_text(encoding='utf-8'))
    for group in summary['groups'].values():
        for check in group['checks']:
            name = check['result_file']
            if not re.fullmatch(r'variations-[a-z0-9-]+\.json',name):
                raise ValueError('Invalid historical result filename.')
            demo_names.append(name)
    files += [ROOT/'demo'/name for name in sorted(set(demo_names))]
    files += sorted((ROOT/'demo/screenshots').glob('*.png'))
    return sorted(set(files))


def build(output):
    if output.suffix.lower() != '.zip':
        raise ValueError('Submission output must end in .zip.')
    validation = json.loads((ROOT/'demo/release-validation.json').read_text(encoding='utf-8'))
    if not validation.get('ready_for_submission'):
        raise ValueError('Complete release verification before packaging.')
    files = submission_files()
    private_key = None
    environment = ROOT/'.env'
    if environment.exists():
        for line in environment.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('OPENAI_API_KEY='):
                private_key = line.split('=',1)[1].strip().strip('"\'').encode()
    hashes = {}
    for source in files:
        relative = source.relative_to(ROOT)
        if source.name == '.env' or source.suffix in {'.sqlite','.db','.pyc','.log'} or any(part.startswith('.venv') or part=='__pycache__' for part in relative.parts):
            raise ValueError('Forbidden submission file.')
        if re.search(r'\bHR\b',source.name,re.I):
            raise ValueError('Submission filenames must use neutral names.')
        data = source.read_bytes()
        if private_key and private_key in data:
            raise ValueError('Private key found in a submission file.')
        if source.suffix in {'.md','.py','.json','.txt'} and re.search(rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}',data):
            raise ValueError('Possible credential found in a submission file.')
        hashes[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    if re.search(r'\bHR\b|SETUP_FOR_HR',readme,re.I):
        raise ValueError('README must be neutral and contain its own setup instructions.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary = output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('insurex-rag/work/','')
        for source in files:
            archive.write(source,'insurex-rag/'+source.relative_to(ROOT).as_posix())
        archive.writestr('insurex-rag/SUBMISSION_MANIFEST.json',json.dumps({'sha256':hashes},indent=2))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity verification failed.')
        for name,digest in hashes.items():
            if hashlib.sha256(archive.read('insurex-rag/'+name)).hexdigest() != digest:
                raise ValueError('Archived file checksum mismatch.')
        names = archive.namelist()
        if sum(name.endswith('.pdf') for name in names) != 5:
            raise ValueError('This assessment submission must include the five supplied brochures.')
        if any(name.endswith(('.sqlite','.db','.pyc','.log','/.env')) for name in names):
            raise ValueError('Unexpected local data in ZIP.')
    temporary.replace(output)
    return {'zip_name':output.name,'file_count':len(files)+1,'bytes':output.stat().st_size,
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'credentials_and_customer_databases_excluded':True,'contents_verified':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'insurex-rag.zip')
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()),indent=2))


if __name__ == '__main__':
    main()
