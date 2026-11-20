"""Explicit developer opt-in: fetch pinned MIT E5 files and verify SHA256."""
import argparse
from hashlib import sha256
from pathlib import Path
import requests
from candidates.story_model_manifest import MODEL_ID, REVISION, FILES, PORTABLE_FILES, artifact_sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination",type=Path,required=True)
    parser.add_argument("--accept-download",action="store_true",help="Explicitly approve official model/tokenizer artifacts (up to ~487 MB)")
    parser.add_argument("--variant",choices=("fp32","int8-vnni"),default="fp32",help="FP32 ~487 MB, portable graph; INT8 ~135 MB is a development CPU-specific artifact")
    args=parser.parse_args()
    if not args.accept_download: parser.error("Pass --accept-download after reviewing model provenance and disk/network cost")
    selected=PORTABLE_FILES if args.variant=="fp32" else FILES
    for name,digest in selected.items():
        target=args.destination/name
        if target.is_file() and artifact_sha256(target)==digest:
            print("Verified existing",name,flush=True);continue
        target.parent.mkdir(parents=True,exist_ok=True)
        url=f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
        print("Downloading",url,flush=True)
        response=requests.get(url,stream=True,timeout=(30,120));response.raise_for_status()
        temp=target.with_suffix(target.suffix+".partial")
        total=0; checksum=sha256()
        with temp.open("wb") as output:
            for chunk in response.iter_content(1024*1024):
                if chunk:
                    total+=len(chunk)
                    if total>500_000_000: raise ValueError("Artifact exceeds declared size budget")
                    checksum.update(chunk);output.write(chunk)
        if checksum.hexdigest()!=digest: raise ValueError("SHA256 mismatch: " + name)
        temp.replace(target)
        print("Verified",name,total,digest,flush=True)

if __name__=="__main__":main()
