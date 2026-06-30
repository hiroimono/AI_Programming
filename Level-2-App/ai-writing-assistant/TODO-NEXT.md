# TODO — Bir Sonraki Oturumda

## 🔴 ÖNCELİK 1: Orphan Doküman Temizliği

**Sorun:**
Bir konuşma silindiğinde, o konuşmaya yüklenmiş dokümanlar `rag-service`
veritabanında öksüz (orphan) olarak kalır. `documents` / `document_chunks`
tablolarında `conversation_id` referansı boş bir konuşmayı işaret eder.
Vektör verisi de Chroma'da kalır. Storage zamanla şişer.

**Mevcut Davranış:**
- Gateway `DELETE /api/writer/conversations/{id}` → sadece `WriterConversation`
  ve cascade ile `WriterMessages` siler.
- `rag-service`'in haberi olmaz, dokümanlar kalır.

**Önerilen Çözüm (3 adım):**

### 1. rag-service: bulk-delete endpoint

`RAG-Service/rag_service/routers/documents.py` içine:

```python
@router.delete("/by-conversation/{conversation_id}", status_code=204)
async def delete_by_conversation(
    conversation_id: UUID,
    svc: DocumentService = Depends(get_document_service),
):
    """Delete all documents (and chunks) belonging to a conversation."""
    await svc.delete_by_conversation(conversation_id)
```

`DocumentService.delete_by_conversation(conversation_id)`:
- `documents` tablosundan ID listesini çek
- Her doc için Chroma'dan vektörleri sil (`collection.delete(where=...)`)
- `document_chunks` ve `documents` satırlarını sil
- Tek transaction içinde

### 2. Gateway: konuşma silmeden önce rag-service'i çağır

`Gateway/src/Gateway.API/Services/WriterConversationService.cs` →
`DeleteConversationAsync`:

```csharp
public async Task<bool> DeleteConversationAsync(Guid id)
{
    var conv = await _db.WriterConversations.FindAsync(id);
    if (conv is null) return false;

    // YENI: rag-service'e haber ver (best-effort, hata olsa bile devam)
    try
    {
        await _ragClient.DeleteByConversationAsync(id);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "rag-service cleanup failed for {ConversationId}", id);
        // konuşma yine de silinsin, sweeper sonra temizler
    }

    _db.WriterConversations.Remove(conv);
    await _db.SaveChangesAsync();
    return true;
}
```

`batch-delete` için de aynı mantık — `Task.WhenAll` ile paralel.

`RagServiceClient` yeni metot:
```csharp
public async Task DeleteByConversationAsync(Guid conversationId)
{
    var token = MintInternalToken();
    var req = new HttpRequestMessage(HttpMethod.Delete,
        $"{_options.BaseUrl}/documents/by-conversation/{conversationId}");
    req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
    var resp = await _http.SendAsync(req);
    resp.EnsureSuccessStatusCode();
}
```

### 3. Background Sweeper (güvenlik ağı)

rag-service içinde günde 1 kez (APScheduler veya basit bir async task):
- `documents.conversation_id`'leri al
- Gateway'e `GET /api/writer/conversations/exists?ids=...` ile sor
- Var olmayanları sil

Bu, Gateway → rag-service çağrısı başarısız olursa veya direkt DB
manipülasyonu olursa yine de temiz tutar.

---

## 🟡 ÖNCELİK 2: Pre-Migration Doc Backfill

Bu commit'ten önce yüklenmiş eski user mesajlarında `attachedDocumentIds`
boş kalacak. İsteğe bağlı bir script:

```sql
-- En naif yaklaşım: o konuşmanın TÜM dokümanlarını ilk user mesajına bağla
UPDATE "WriterMessages" m
SET "AttachedDocumentIds" = (
  SELECT array_agg(d.id)
  FROM rag.documents d
  WHERE d.conversation_id = m."ConversationId"
)
WHERE m."Role" = 'user'
  AND m."AttachedDocumentIds" = '{}'::uuid[]
  AND m."CreatedAt" = (
    SELECT MIN("CreatedAt") FROM "WriterMessages" m2
    WHERE m2."ConversationId" = m."ConversationId" AND m2."Role" = 'user'
  );
```

Ama bu yanlış olabilir — kullanıcı dokümanı 3. mesajda yüklemiş olabilir.
Karar: backfill yapma, geçmiş veride chip görünmemesini kabul et.

---

## 🟢 ÖNCELİK 3: UI / UX

- [ ] Chip'lere "yüklendi" anında çok kısa fade-in animasyonu
- [ ] Source paneli açıldığında ilk satır focus → klavye nav
- [ ] PDF preview modal — Esc tuşu ile kapanma
- [ ] "Tüm konuşmaları sil" toplu işlem için onay modalı (şu an sadece per-conv)
