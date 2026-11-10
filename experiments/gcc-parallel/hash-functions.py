import hashlib, json, pathlib, re, sys
root=pathlib.Path(sys.argv[1]); parts=sorted(root.glob(root.name+'.part*.c'))+[root/(root.name+'.c')]
start=re.compile(rb'^int (F_[0-9a-f]+)\(plaid_state \*s, u64 ret\) \{\r?\n$')
functions={}
for path in parts:
    with path.open('rb') as source:
        name=None; body=[]
        for line in source:
            if name is None:
                match=start.match(line)
                if match: name=match.group(1).decode(); body=[line]
            else:
                body.append(line)
                if line in (b'}\n',b'}\r\n'):
                    if name in functions: raise ValueError('duplicate '+name)
                    functions[name]=hashlib.sha256(b''.join(body)).hexdigest(); name=None
        if name is not None: raise ValueError('unterminated '+name)
if not functions: raise ValueError('no functions')
canonical=''.join(k+' '+v+'\n' for k,v in sorted(functions.items())).encode()
print(json.dumps({'count':len(functions),'canonical_sha256':hashlib.sha256(canonical).hexdigest(),'functions':functions},sort_keys=True))
