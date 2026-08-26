export type BotConfig = {
  chat_id: number | null;
  welcome_text: string;
  questionnaire_timeout_minutes: number;
  questionnaire_kick_enabled: boolean;
  logging_enabled: boolean;
  log_flush_interval_minutes: number;
  channel_ids: number[];
  inactive_warning_enabled: boolean;
  inactive_check_hours: number;
  inactive_warning_text: string;
  forbidden_words: string[];
  mute_seconds: number;
  mute_notice: string;
  long_post_chars: number;
  long_post_burst: number;
  long_post_burst_seconds: number;
  blacklist: number[];
  ollama_model: string;
  nlp_profanity: boolean;
  missing_term_reply: string;
  activity_reminders: number[];
  timezone: string;
};

export const defaultConfig: BotConfig = {
  chat_id: null,
  welcome_text:
    "Добро пожаловать. Ответьте на это сообщение анкетой: кто вы, чем занимаетесь и зачем пришли в чат. Можно несколькими сообщениями.",
  questionnaire_timeout_minutes: 60,
  questionnaire_kick_enabled: true,
  logging_enabled: true,
  log_flush_interval_minutes: 60,
  channel_ids: [],
  inactive_warning_enabled: true,
  inactive_check_hours: 24,
  inactive_warning_text:
    "{mention}, вы сейчас наименее активны в чате. Если молчание продолжится, вас могут исключить.",
  forbidden_words: ["блять", "хуй", "пизд", "ебан", "сука"],
  mute_seconds: 3600,
  mute_notice: "Сообщение удалено. Мут на {minutes} мин. за запрещённые выражения.",
  long_post_chars: 800,
  long_post_burst: 3,
  long_post_burst_seconds: 120,
  blacklist: [],
  ollama_model: "llama3.2",
  nlp_profanity: false,
  missing_term_reply: "В базе терминов этого нет.",
  activity_reminders: [1440, 180, 60],
  timezone: "Europe/Moscow",
};

export type NlpJob = {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  created_at: number;
};
