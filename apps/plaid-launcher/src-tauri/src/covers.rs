//! Box art from libretro-thumbnails (Named_Boxarts), matched by title and cached on disk.

use crate::rom::match_key;
use std::io::Read as _;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, SystemTime};

const REPO: &str = "libretro-thumbnails/Nintendo_-_Nintendo_64";
const AGENT: &str = "plaid-launcher";

fn get(url: &str) -> Result<ureq::Response, String> {
    ureq::get(url)
        .set("User-Agent", AGENT)
        .timeout(Duration::from_secs(20))
        .call()
        .map_err(|e| e.to_string())
}

/// Box-art names (No-Intro style, without ".png"), refreshed weekly.
fn index(cache: &Path) -> Result<Vec<String>, String> {
    let file = cache.join("index.json");
    let fresh = std::fs::metadata(&file)
        .and_then(|m| m.modified())
        .is_ok_and(|t| {
            SystemTime::now().duration_since(t).unwrap_or_default() < Duration::from_secs(7 * 86400)
        });
    if fresh
        && let Ok(names) = std::fs::read(&file)
            .map_err(|e| e.to_string())
            .and_then(|b| serde_json::from_slice(&b).map_err(|e| e.to_string()))
    {
        return Ok(names);
    }
    let body = get(&format!(
        "https://api.github.com/repos/{REPO}/git/trees/master?recursive=1"
    ))?
    .into_string()
    .map_err(|e| e.to_string())?;
    let tree: serde_json::Value = serde_json::from_str(&body).map_err(|e| e.to_string())?;
    let names: Vec<String> = tree["tree"]
        .as_array()
        .ok_or("unexpected thumbnail index")?
        .iter()
        .filter_map(|e| {
            e["path"]
                .as_str()?
                .strip_prefix("Named_Boxarts/")?
                .strip_suffix(".png")
                .map(str::to_string)
        })
        .collect();
    std::fs::create_dir_all(cache).map_err(|e| e.to_string())?;
    std::fs::write(&file, serde_json::to_vec(&names).unwrap()).map_err(|e| e.to_string())?;
    Ok(names)
}

/// The best box-art name: the exact file name if listed, else the same base title,
/// preferring the ROM's region and then the plainest variant (no "(Debug)", "(GameCube)" ...).
pub fn best_match<'a>(
    names: &'a [String],
    stem: &str,
    internal: &str,
    region: &str,
) -> Option<&'a String> {
    if let Some(exact) = names.iter().find(|n| n.as_str() == stem) {
        return Some(exact);
    }
    let base = |s: &str| match_key(s.split(['(', '[']).next().unwrap_or(s));
    [base(stem), match_key(internal)]
        .into_iter()
        .filter(|k| !k.is_empty())
        .find_map(|key| {
            let hits: Vec<&String> = names.iter().filter(|n| base(n) == key).collect();
            let local: Vec<&String> = hits
                .iter()
                .copied()
                .filter(|n| n.contains(&format!("({region}")))
                .collect();
            let pool = if local.is_empty() { hits } else { local };
            pool.into_iter().min_by_key(|n| (n.len(), n.as_str()))
        })
}

fn encode(name: &str) -> String {
    name.bytes()
        .map(|b| {
            if b.is_ascii_alphanumeric() || b"-_.~".contains(&b) {
                (b as char).to_string()
            } else {
                format!("%{b:02X}")
            }
        })
        .collect()
}

const PNG: &[u8] = b"\x89PNG";

/// The box art named `name`, following libretro's git symlinks: raw.githubusercontent
/// serves a symlink as its target path, e.g. "Star Fox 64 (USA).png".
fn download(name: &str) -> Result<Vec<u8>, String> {
    let mut name = name.to_string();
    for _ in 0..4 {
        let mut bytes = Vec::new();
        get(&format!(
            "https://raw.githubusercontent.com/{REPO}/master/Named_Boxarts/{}.png",
            encode(&name)
        ))?
        .into_reader()
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
        if bytes.starts_with(PNG) {
            return Ok(bytes);
        }
        let target = std::str::from_utf8(&bytes)
            .ok()
            .filter(|t| t.len() < 512)
            .ok_or("box art is not a PNG")?;
        name = link_target(target).ok_or("box art is not a PNG")?;
    }
    Err("box art symlink chain too long".into())
}

/// The box-art name a symlink's text points at.
fn link_target(text: &str) -> Option<String> {
    let file = text.trim().rsplit(['/', '\\']).next()?;
    file.strip_suffix(".png")
        .filter(|n| !n.is_empty())
        .map(str::to_string)
}

static INDEX_LOCK: Mutex<()> = Mutex::new(());

/// Local path of the cover for `id`, downloading it on first use.
pub fn cover(
    cache: &Path,
    id: &str,
    stem: &str,
    internal: &str,
    region: &str,
) -> Result<PathBuf, String> {
    let file = cache.join(format!("{id}.png"));
    if std::fs::read(&file).is_ok_and(|b| b.starts_with(PNG)) {
        return Ok(file);
    }
    // one index fetch for the whole library: the GitHub API allows 60 anonymous calls an hour
    let names = {
        let _guard = INDEX_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        index(cache)?
    };
    let name = best_match(&names, stem, internal, region).ok_or("no box art found")?;
    std::fs::write(&file, download(name)?).map_err(|e| e.to_string())?;
    Ok(file)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_goodn64_names_to_no_intro_by_region() {
        let names: Vec<String> = [
            "Legend of Zelda, The - Ocarina of Time (Europe)",
            "Legend of Zelda, The - Ocarina of Time (USA)",
            "Star Fox 64 (USA) (Rev 1)",
            "Mario Party 2 (USA)",
        ]
        .map(String::from)
        .to_vec();
        let oot = best_match(
            &names,
            "Legend of Zelda, The - Ocarina of Time (U) (V1.2) [!]",
            "THE LEGEND OF ZELDA",
            "USA",
        );
        assert_eq!(
            oot.map(String::as_str),
            Some("Legend of Zelda, The - Ocarina of Time (USA)")
        );
        assert_eq!(
            best_match(&names, "sf64", "Star Fox 64", "USA").map(String::as_str),
            Some("Star Fox 64 (USA) (Rev 1)")
        );
        assert_eq!(best_match(&names, "unknown", "NOPE", "USA"), None);
        assert_eq!(encode("A, B (C)"), "A%2C%20B%20%28C%29");
        let variants: Vec<String> = [
            "Legend of Zelda, The - Majora's Mask (USA) (GameCube)",
            "Legend of Zelda, The - Majora's Mask (USA) - SymbolicLink",
            "Legend of Zelda, The - Majora's Mask (USA)",
            "Banjo-Kazooie (USA)",
            "Banjo-Kazooie (USA) (Rev 1)",
        ]
        .map(String::from)
        .to_vec();
        let mm = best_match(&variants, "Majora (U)", "ZELDA MAJORA'S MASK", "USA");
        assert_eq!(mm, None); // base titles differ and the header name is not a box-art title
        let mm = best_match(
            &variants,
            "Legend of Zelda, The - Majora's Mask [!]",
            "",
            "USA",
        );
        assert_eq!(
            mm.map(String::as_str),
            Some("Legend of Zelda, The - Majora's Mask (USA)")
        );
        let bk = best_match(&variants, "Banjo-Kazooie (USA) (Rev 1)", "", "USA");
        assert_eq!(bk.map(String::as_str), Some("Banjo-Kazooie (USA) (Rev 1)"));
        assert_eq!(
            link_target("Star Fox 64 (USA).png").as_deref(),
            Some("Star Fox 64 (USA)")
        );
        assert_eq!(
            link_target("../Named_Boxarts/Lylat Wars (Europe).png\n").as_deref(),
            Some("Lylat Wars (Europe)")
        );
    }
}
