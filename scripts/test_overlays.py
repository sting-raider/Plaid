"""ROM-owned file and overlay tables through the public CLI; synthetic bytes only."""
from pathlib import Path
import json, os, struct, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]

def main():
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(prefix='overlay-cli-',dir=ROOT/'target') as directory:
        p=Path(directory);rom=bytearray(0x3000)
        def put(data,offset,words):data[offset:offset+4*len(words)]=struct.pack('>'+str(len(words))+'I',*words)
        put(rom,0,[0x80371240]);put(rom,0x1000,[0x1000ffff,0])
        overlay=bytearray(64)
        put(overlay,0,[0x3c088080,0x25080010,0x03e00008,0])
        put(overlay,16,[0x80800010,0,0,0])
        put(overlay,32,[16,16,0,0,3,0x45000000,0x46000004,0x82000000])
        overlay.extend(struct.pack('>I',36))
        rom[0x2000:0x2000+len(overlay)]=overlay
        put(rom,0x80,[0,0x80,0,0, 0x80,0xc0,0x80,0, 0x3000,0x3000+len(overlay),0x2000,0])
        put(rom,0x1020,[0x3000,0x3000+len(overlay),0x80800000,0x80800000+len(overlay)])
        source=p/'input.z64';source.write_bytes(rom);map_path=p/'map.json';out=p/'overlays.json'
        subprocess.run([str(exe),'discover',str(source),'0x1000','0x80000000','0x40','0x80000000',str(map_path)],check=True,capture_output=True)
        subprocess.run([str(exe),'inspect-overlays',str(source),str(map_path),str(out)],check=True,capture_output=True)
        doc=json.loads(out.read_bytes());assert doc['format']=='plaid-overlay-candidates-v0'
        entries=doc['images'][0]['overlays'];assert len(entries)==1
        assert entries[0]['link']==0x80800000 and entries[0]['table_offsets']==[32]
        assert [r['kind'] for r in entries[0]['layout']['relocations']]==[5,6,2]
        assert entries[0]['layout']['file_size']==68
        for protected in (source,map_path):
            before=protected.read_bytes()
            bad=subprocess.run([str(exe),'inspect-overlays',str(source),str(map_path),str(protected)],capture_output=True)
            assert bad.returncode!=0 and protected.read_bytes()==before
        # Discovery must reject a table claiming an incompatible link span.
        put(rom,0x102c,[0x80800008]);source.write_bytes(rom)
        subprocess.run([str(exe),'discover',str(source),'0x1000','0x80000000','0x40','0x80000000',str(map_path)],check=True,capture_output=True)
        bad=subprocess.run([str(exe),'inspect-overlays',str(source),str(map_path),str(out)],capture_output=True)
        assert bad.returncode!=0 and b'overlay table range differs' in bad.stderr
    print('PASS synthetic ROM tables -> overlay catalog and contradictory range rejection')

if __name__=='__main__':main()
