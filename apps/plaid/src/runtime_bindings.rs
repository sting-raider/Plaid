//! Restore newly consumed optional metadata from the exact original declaration.
use super::*;

pub(super) fn bind(map: &mut ProgramMap, path: &String) -> Result<(), String> {
    let (functions, evidence, _, _, _, sizes, globals) = runtime_declarations(Some(path))?;
    let (id, source) = evidence.ok_or("runtime declaration evidence absent")?;
    if map.evidence.get(&id) != Some(&source) {
        return Err("runtime declaration differs from original source evidence".into());
    }
    let mut bindings = map.runtime_running_thread.clone();
    for (entry, global) in globals {
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
                || bindings.get(address).is_some_and(|old| *old != global)
            {
                return Err("runtime binding differs from source identity or ABI".into());
            }
            found = true;
            bindings.insert(address.clone(), global);
        }
        if !found {
            return Err("runtime binding has no original native entry".into());
        }
    }
    let mut candidate = map.clone();
    candidate.runtime_running_thread = bindings;
    candidate.validate()?;
    *map = candidate;
    Ok(())
}
