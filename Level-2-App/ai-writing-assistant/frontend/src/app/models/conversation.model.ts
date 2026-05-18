export interface Conversation {
  id: string;
  title: string;
  titleGenCount: number;
  isTitleManual: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateTitleResult {
  title: string;
  new_score: number;
  old_score: number;
}
