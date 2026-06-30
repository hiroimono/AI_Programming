export interface DocumentItem {
  id: string;
  file_name: string;
  file_type: string;
  mime_type: string;
  file_size_bytes: number;
  status: 'pending' | 'ready' | 'failed';
  chunk_count: number;
  created_at: string;
  error_message?: string | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  status: 'pending' | 'ready' | 'failed';
  chunk_count: number;
}

export interface SourceCitation {
  document_id: string;
  document_filename: string;
  chunk_index: number;
  distance: number;
  preview: string;
}
