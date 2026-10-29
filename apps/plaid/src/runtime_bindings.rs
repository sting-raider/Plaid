//! Restore newly consumed optional metadata from the exact original declaration.
use super::*;

pub(super) fn bind(map: &mut ProgramMap, path: &String) -> Result<(), String> {
    let (functions, evidence, _, _, _, sizes, globals, kernel_globals) =
        runtime_declarations(Some(path))?;
    let (id, source) = evidence.ok_or("runtime declaration evidence absent")?;
    if map.evidence.get(&id) != Some(&source) {
        return Err("runtime declaration differs from original source evidence".into());
    }
    let mut bindings = map.runtime_running_thread.clone();
    let mut kernel_bindings = map.runtime_kernel_global.clone();
    let entries: BTreeSet<_> = globals
        .keys()
        .chain(kernel_globals.keys())
        .copied()
        .collect();
    for entry in entries {
        let (_, name, callbacks) = functions
            .iter()
            .find(|(pc, _, _)| *pc == entry)
            .ok_or("binding has no runtime declaration")?;
        let mut found = false;
        for (address, function) in &map.runtime_functions {
            if address.pc != entry {
                continue;
            }
            if function.name != *name
                || function.callbacks != *callbacks
                || function.source_size != sizes.get(&entry).copied()
                || !function.evidence.contains(&id)
                || globals
                    .get(&entry)
                    .is_some_and(|global| bindings.get(address).is_some_and(|old| old != global))
                || kernel_globals.get(&entry).is_some_and(|binding| {
                    kernel_bindings
                        .get(address)
                        .is_some_and(|old| old != binding)
                })
            {
                return Err("runtime binding differs from source identity or ABI".into());
            }
            found = true;
            if let Some(global) = globals.get(&entry) {
                bindings.insert(address.clone(), *global);
            }
            if let Some(binding) = kernel_globals.get(&entry) {
                kernel_bindings.insert(address.clone(), *binding);
            }
        }
        if !found {
            return Err("runtime binding has no original native entry".into());
        }
    }
    let mut candidate = map.clone();
    candidate.runtime_running_thread = bindings;
    candidate.runtime_kernel_global = kernel_bindings;
    candidate.validate()?;
    *map = candidate;
    Ok(())
}
