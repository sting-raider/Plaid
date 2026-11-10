//! Discord Rich Presence while a game runs: "Playing Plaid", the game's name, the Plaid logo.

use discord_rich_presence::{activity, DiscordIpc, DiscordIpcClient};

/// The "Plaid" application in the Discord developer portal; its art asset "plaid" is the logo.
const APP_ID: &str = "1569834758970548378";

/// Shows the game as being played until the returned guard is dropped.
/// Discord not running is not an error: there is just no presence.
pub fn playing(game: &str) -> Option<Presence> {
    let mut client = DiscordIpcClient::new(APP_ID);
    client.connect().ok()?;
    let started = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    client
        .set_activity(
            activity::Activity::new()
                .details(game)
                .state("Recompiled natively with Plaid")
                .assets(
                    activity::Assets::new()
                        .large_image("plaid")
                        .large_text("Plaid"),
                )
                .timestamps(activity::Timestamps::new().start(started)),
        )
        .ok()?;
    Some(Presence(client))
}

pub struct Presence(DiscordIpcClient);

impl Drop for Presence {
    fn drop(&mut self) {
        let _ = self.0.clear_activity();
        let _ = self.0.close();
    }
}
