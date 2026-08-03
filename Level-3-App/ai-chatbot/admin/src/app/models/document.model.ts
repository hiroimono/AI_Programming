/**
 * Document (RAG knowledge base entry) wire type. Mirrors backend DocumentOut.
 *
 * A `status: 'ready'` document with `chunk_count === 0` means the file was
 * accepted and processed but produced no indexable chunks (too short/empty) —
 * the Knowledge tab surfaces this as an explicit warning so the admin knows
 * the bot cannot answer from that file.
 */

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed';

export interface DocumentItem {
  id: string;
  file_name: string;
  file_type: string;
  mime_type: string | null;
  file_size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  created_at: string;
}
