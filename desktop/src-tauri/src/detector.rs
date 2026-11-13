use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum MeetingPlatform {
    GoogleMeet,
    Discord,
    Zoom,
    MicrosoftTeams,
    Generic,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WindowInfo {
    pub owner_name: String,
    pub title: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DetectedMeeting {
    pub platform: MeetingPlatform,
    pub title: String,
    pub identifier: String,
}

pub struct DetectorEngine {
    meet_regex: Regex,
    discord_regex: Regex,
    zoom_regex: Regex,
    teams_regex: Regex,
}

impl DetectorEngine {
    pub fn new() -> Self {
        Self {
            // Suporta hífen comum (-), en-dash (– \u{2013}) e em-dash (— \u{2014})
            meet_regex: Regex::new(r"(?i)Meet\s*[\u{2013}\u{2014}-]\s*([a-z0-9-]+)").unwrap(),
            discord_regex: Regex::new(r"(?i)(Discord.*(?:Voice|Voz|Chamada|Call)|\(Voice\)|\(Voz\))").unwrap(),
            zoom_regex: Regex::new(r"(?i)(Zoom\s+Meeting|Reuni[aã]o\s+Zoom|Zoom\s+Cloud\s+Meetings)").unwrap(),
            teams_regex: Regex::new(r"(?i)(Meeting|Reuni[aã]o)\s*\|\s*Microsoft\s+Teams|Microsoft\s+Teams\s+Meeting").unwrap(),
        }
    }

    /// Analisa uma janela aberta (título e processo proprietário) e identifica se pertence a uma chamada.
    pub fn inspect_window(&self, window: &WindowInfo) -> Option<DetectedMeeting> {
        let title = window.title.trim();
        let owner = window.owner_name.trim();

        if title.is_empty() && owner.is_empty() {
            return None;
        }

        let title_lower = title.to_lowercase();

        // 1. Google Meet (normalmente executado dentro do navegador)
        if let Some(caps) = self.meet_regex.captures(title) {
            let identifier = caps.get(1).map_or("meet-call", |m| m.as_str()).to_string();
            return Some(DetectedMeeting {
                platform: MeetingPlatform::GoogleMeet,
                title: title.to_string(),
                identifier: format!("google-meet:{}", identifier),
            });
        }
        if title.contains("Meet –") || title.contains("Meet —") || title.contains("Meet -") || title.contains("Google Meet") {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::GoogleMeet,
                title: title.to_string(),
                identifier: format!("google-meet:{}", title),
            });
        }

        // 2. Discord (inspeção combinada de título e nome do processo)
        let is_discord_owner = owner.eq_ignore_ascii_case("Discord") || owner.eq_ignore_ascii_case("Discord.exe");
        if self.discord_regex.is_match(title)
            || (is_discord_owner && (title_lower.contains("voice") || title_lower.contains("voz") || title_lower.contains("call") || title_lower.contains("chamada")))
        {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::Discord,
                title: if !title.is_empty() { title.to_string() } else { "Discord Voice Call".to_string() },
                identifier: format!("discord:{}", if !title.is_empty() { title } else { "call" }),
            });
        }

        // 3. Zoom
        let is_zoom_owner = owner.eq_ignore_ascii_case("zoom.us") || owner.eq_ignore_ascii_case("Zoom.exe") || owner.eq_ignore_ascii_case("Zoom");
        if self.zoom_regex.is_match(title)
            || (is_zoom_owner && (title_lower.contains("meeting") || title_lower.contains("reunião") || title_lower.contains("reuniao") || title.is_empty()))
        {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::Zoom,
                title: if !title.is_empty() { title.to_string() } else { "Zoom Meeting".to_string() },
                identifier: format!("zoom:{}", if !title.is_empty() { title } else { "active" }),
            });
        }

        // 4. Microsoft Teams
        let is_teams_owner = owner.to_lowercase().contains("teams") || owner.eq_ignore_ascii_case("ms-teams.exe");
        if self.teams_regex.is_match(title)
            || (is_teams_owner && (title_lower.contains("meeting") || title_lower.contains("reunião") || title_lower.contains("reuniao") || title_lower.contains("chamada")))
        {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::MicrosoftTeams,
                title: if !title.is_empty() { title.to_string() } else { "Teams Meeting".to_string() },
                identifier: format!("teams:{}", if !title.is_empty() { title } else { "active" }),
            });
        }

        None
    }
}

/// Evita disparar alertas repetidos para a mesma reunião a cada ciclo de polling
pub struct MeetingCooldownTracker {
    cooldown_duration: Duration,
    history: Mutex<HashMap<String, Instant>>,
}

impl MeetingCooldownTracker {
    pub fn new(cooldown_secs: u64) -> Self {
        Self {
            cooldown_duration: Duration::from_secs(cooldown_secs),
            history: Mutex::new(HashMap::new()),
        }
    }

    /// Retorna `true` se a reunião for inédita ou se o cooldown já expirou.
    pub fn should_notify(&self, identifier: &str) -> bool {
        let mut history = self.history.lock().unwrap();
        let now = Instant::now();

        if let Some(&last_seen) = history.get(identifier) {
            if now.duration_since(last_seen) < self.cooldown_duration {
                return false; // Ainda em cooldown
            }
        }

        history.insert(identifier.to_string(), now);
        true
    }

    /// Limpa o cooldown para permitir nova notificação explícita
    pub fn reset(&self, identifier: &str) {
        let mut history = self.history.lock().unwrap();
        history.remove(identifier);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_google_meet_hyphen() {
        let engine = DetectorEngine::new();
        let win = WindowInfo {
            owner_name: "Google Chrome".to_string(),
            title: "Meet - abc-defg-hij - Google Chrome".to_string(),
        };
        let detected = engine.inspect_window(&win).expect("Should detect Google Meet with hyphen");
        assert_eq!(detected.platform, MeetingPlatform::GoogleMeet);
        assert_eq!(detected.identifier, "google-meet:abc-defg-hij");
    }

    #[test]
    fn test_google_meet_en_dash() {
        let engine = DetectorEngine::new();
        let win = WindowInfo {
            owner_name: "Brave Browser".to_string(),
            title: "Meet \u{2013} xyz-uvwx-rst".to_string(), // en-dash (–)
        };
        let detected = engine.inspect_window(&win).expect("Should detect Google Meet with en-dash");
        assert_eq!(detected.platform, MeetingPlatform::GoogleMeet);
        assert_eq!(detected.identifier, "google-meet:xyz-uvwx-rst");
    }

    #[test]
    fn test_google_meet_em_dash() {
        let engine = DetectorEngine::new();
        let win = WindowInfo {
            owner_name: "Arc".to_string(),
            title: "Meet \u{2014} 123-4567-890".to_string(), // em-dash (—)
        };
        let detected = engine.inspect_window(&win).expect("Should detect Google Meet with em-dash");
        assert_eq!(detected.platform, MeetingPlatform::GoogleMeet);
        assert_eq!(detected.identifier, "google-meet:123-4567-890");
    }

    #[test]
    fn test_google_meet_fallback() {
        let engine = DetectorEngine::new();
        let win = WindowInfo {
            owner_name: "Google Chrome".to_string(),
            title: "Reunião de Alinhamento - Google Meet".to_string(),
        };
        let detected = engine.inspect_window(&win).expect("Should detect Google Meet fallback");
        assert_eq!(detected.platform, MeetingPlatform::GoogleMeet);
        assert!(detected.identifier.starts_with("google-meet:"));
    }

    #[test]
    fn test_discord_voice_and_call() {
        let engine = DetectorEngine::new();

        // Discord app with Voice in title
        let win1 = WindowInfo {
            owner_name: "Discord".to_string(),
            title: "General (Voice) - Discord".to_string(),
        };
        let d1 = engine.inspect_window(&win1).expect("Should detect Discord voice");
        assert_eq!(d1.platform, MeetingPlatform::Discord);

        // Discord process with Voz in Portuguese
        let win2 = WindowInfo {
            owner_name: "Discord.exe".to_string(),
            title: "#sala-de-voz".to_string(),
        };
        let d2 = engine.inspect_window(&win2).expect("Should detect Discord voice pt-BR");
        assert_eq!(d2.platform, MeetingPlatform::Discord);

        // Discord Call
        let win3 = WindowInfo {
            owner_name: "Discord".to_string(),
            title: "Discord Chamada em Grupo".to_string(),
        };
        let d3 = engine.inspect_window(&win3).expect("Should detect Discord call");
        assert_eq!(d3.platform, MeetingPlatform::Discord);
    }

    #[test]
    fn test_zoom_meeting() {
        let engine = DetectorEngine::new();

        let win1 = WindowInfo {
            owner_name: "zoom.us".to_string(),
            title: "Zoom Meeting".to_string(),
        };
        let d1 = engine.inspect_window(&win1).expect("Should detect Zoom Meeting");
        assert_eq!(d1.platform, MeetingPlatform::Zoom);

        let win2 = WindowInfo {
            owner_name: "Zoom.exe".to_string(),
            title: "Reunião Zoom de Sergio".to_string(),
        };
        let d2 = engine.inspect_window(&win2).expect("Should detect Zoom pt-BR");
        assert_eq!(d2.platform, MeetingPlatform::Zoom);

        let win3 = WindowInfo {
            owner_name: "zoom.us".to_string(),
            title: "".to_string(),
        };
        let d3 = engine.inspect_window(&win3).expect("Should detect Zoom active window with empty title");
        assert_eq!(d3.platform, MeetingPlatform::Zoom);
    }

    #[test]
    fn test_microsoft_teams() {
        let engine = DetectorEngine::new();

        let win1 = WindowInfo {
            owner_name: "ms-teams.exe".to_string(),
            title: "Daily Standup Meeting".to_string(),
        };
        let d1 = engine.inspect_window(&win1).expect("Should detect Teams Meeting with ms-teams.exe");
        assert_eq!(d1.platform, MeetingPlatform::MicrosoftTeams);

        let win2 = WindowInfo {
            owner_name: "Teams".to_string(),
            title: "Reunião | Microsoft Teams".to_string(),
        };
        let d2 = engine.inspect_window(&win2).expect("Should detect Teams Reunião");
        assert_eq!(d2.platform, MeetingPlatform::MicrosoftTeams);

        let win3 = WindowInfo {
            owner_name: "Microsoft Teams".to_string(),
            title: "Microsoft Teams Meeting".to_string(),
        };
        let d3 = engine.inspect_window(&win3).expect("Should detect Teams Meeting standard");
        assert_eq!(d3.platform, MeetingPlatform::MicrosoftTeams);
    }

    #[test]
    fn test_non_meeting_windows_return_none() {
        let engine = DetectorEngine::new();

        let non_meetings = vec![
            WindowInfo {
                owner_name: "Google Chrome".to_string(),
                title: "GitHub - cortechx-zumo - Pull Requests".to_string(),
            },
            WindowInfo {
                owner_name: "Code".to_string(),
                title: "detector.rs - CortechX Zumo - Visual Studio Code".to_string(),
            },
            WindowInfo {
                owner_name: "Discord".to_string(),
                title: "#text-only-channel | Gaming Server".to_string(),
            },
            WindowInfo {
                owner_name: "Teams".to_string(),
                title: "Chat | Microsoft Teams".to_string(),
            },
            WindowInfo {
                owner_name: "Spotify".to_string(),
                title: "Spotify Free".to_string(),
            },
            WindowInfo {
                owner_name: "".to_string(),
                title: "".to_string(),
            },
        ];

        for win in non_meetings {
            assert!(
                engine.inspect_window(&win).is_none(),
                "Window '{:?}' should not be detected as a meeting",
                win
            );
        }
    }

    #[test]
    fn test_cooldown_tracker_and_reset() {
        let tracker = MeetingCooldownTracker::new(60);

        // First notification should be accepted
        assert!(tracker.should_notify("test-meeting-1"));

        // Subsequent notification within cooldown window should be suppressed
        assert!(!tracker.should_notify("test-meeting-1"));

        // Different meeting identifier should not be suppressed
        assert!(tracker.should_notify("test-meeting-2"));
        assert!(!tracker.should_notify("test-meeting-2"));

        // After reset, previous meeting identifier should be accepted again
        tracker.reset("test-meeting-1");
        assert!(tracker.should_notify("test-meeting-1"));
    }

    #[test]
    fn test_cooldown_tracker_expiration() {
        let tracker = MeetingCooldownTracker::new(0);

        assert!(tracker.should_notify("instant-meeting"));
        std::thread::sleep(Duration::from_millis(5));
        assert!(tracker.should_notify("instant-meeting"));
    }
}
