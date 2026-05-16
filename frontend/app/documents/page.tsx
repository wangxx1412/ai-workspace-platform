"use client";

import { useEffect, useState } from "react";
import AppNav from "../components/AppNav";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/**
 * Document item shown in the document sidebar/list.
 * 文档列表里显示的文档结构。
 */
type DocumentItem = {
  id: string;
  filename: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

/**
 * Detailed document status returned by:
 * GET /documents/{document_id}
 *
 * 某个文档的详情，由这个接口返回：
 * GET /documents/{document_id}
 */
type DocumentDetail = {
  id: string;
  filename: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
};

/**
 * Response from:
 * POST /documents/{document_id}/ask
 *
 * 文档问答接口返回结构。
 */
type AskResponse = {
  answer: string;
  sources: {
    chunk_id: string;
    filename: string;
    content: string;
    page_number: number | null;
    chunk_index: number;
  }[];
};

/**
 * Helper function to format date.
 * 格式化日期的小工具。
 */
function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

/**
 * Helper function to render status badge.
 * 渲染文档状态 badge。
 *
 * We intentionally keep this simple.
 * 这里故意保持简单，不引入额外 UI library。
 */
function getStatusLabel(status: string) {
  switch (status) {
    case "uploaded":
      return "Uploaded";
    case "processing":
      return "Processing";
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

export default function DocumentsPage() {
  /**
   * List of uploaded documents.
   * 已上传文档列表。
   */
  const [documents, setDocuments] = useState<DocumentItem[]>([]);

  /**
   * Currently selected document id.
   * 当前选中的文档 ID。
   */
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  );

  /**
   * Detail of selected document.
   * 当前选中文档的详情。
   *
   * This includes status and chunk_count.
   * 包括 status 和 chunk_count。
   */
  const [selectedDocumentDetail, setSelectedDocumentDetail] =
    useState<DocumentDetail | null>(null);

  /**
   * Selected file from file input.
   * 用户在 input 里选择的文件。
   */
  const [file, setFile] = useState<File | null>(null);

  /**
   * User question for selected document.
   * 用户针对选中文档提出的问题。
   */
  const [question, setQuestion] = useState("");

  /**
   * AI answer returned by backend.
   * 后端返回的 AI 答案。
   */
  const [answer, setAnswer] = useState("");

  /**
   * Source chunks returned by backend.
   * 后端返回的 source chunks。
   *
   * These are used as citations.
   * 这些用于 citation / 来源展示。
   */
  const [sources, setSources] = useState<AskResponse["sources"]>([]);

  /**
   * Upload loading state.
   * 上传中的 loading 状态。
   */
  const [isUploading, setIsUploading] = useState(false);

  /**
   * Asking loading state.
   * 提问中的 loading 状态。
   */
  const [isAsking, setIsAsking] = useState(false);

  /**
   * User-facing error message.
   * 展示给用户看的错误信息。
   */
  const [error, setError] = useState("");

  /**
   * Load all uploaded documents.
   * 加载所有已上传文档。
   *
   * Backend endpoint:
   * GET /documents
   */
  async function loadDocuments() {
    const response = await fetch(`${API_BASE_URL}/documents`);

    if (!response.ok) {
      throw new Error("Failed to load documents");
    }

    const data: DocumentItem[] = await response.json();
    setDocuments(data);
  }

  /**
   * Load detail for one document.
   * 加载单个文档详情。
   *
   * Backend endpoint:
   * GET /documents/{document_id}
   *
   * This is used for:
   * 用途：
   * - checking status
   * - showing chunk_count
   * - polling processing progress
   */
  async function loadDocumentDetail(documentId: string) {
    const response = await fetch(`${API_BASE_URL}/documents/${documentId}`);

    if (!response.ok) {
      throw new Error("Failed to load document detail");
    }

    const data: DocumentDetail = await response.json();

    setSelectedDocumentDetail(data);

    return data;
  }

  /**
   * Upload selected PDF document.
   * 上传用户选择的 PDF 文档。
   *
   * Important:
   * 重要：
   *
   * Backend expects multipart/form-data, not JSON.
   * 后端期待 multipart/form-data，不是 JSON。
   *
   * So we use FormData:
   * 所以这里使用 FormData：
   *
   * formData.append("file", file)
   */
  async function uploadDocument() {
    if (!file) return;

    setError("");
    setIsUploading(true);
    setAnswer("");
    setSources([]);

    try {
      const formData = new FormData();

      /**
       * The key must be "file" because backend endpoint is:
       * key 必须是 "file"，因为后端接口是：
       *
       * file: UploadFile = File(...)
       */
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      /**
       * Day 7 backend returns immediately:
       * Day 7 后端会立刻返回：
       *
       * {
       *   id,
       *   filename,
       *   status: "uploaded"
       * }
       *
       * Actual extraction/chunking/embedding happens in background.
       * 真正的解析、chunk、embedding 会在后台继续做。
       */
      const uploadedDocument: DocumentItem = await response.json();

      /**
       * Select uploaded document immediately.
       * 上传后立刻选中这个文档。
       */
      setSelectedDocumentId(uploadedDocument.id);

      /**
       * Clear file input state.
       * 清空当前 file state。
       */
      setFile(null);

      /**
       * Refresh document list and detail.
       * 刷新文档列表和文档详情。
       */
      await loadDocuments();
      await loadDocumentDetail(uploadedDocument.id);
    } catch (err) {
      console.error(err);
      setError("Failed to upload document.");
    } finally {
      setIsUploading(false);
    }
  }

  /**
   * Ask a question about selected document.
   * 针对选中文档提问。
   *
   * Backend endpoint:
   * POST /documents/{document_id}/ask
   */
  async function askDocument() {
    if (!selectedDocumentId || !question.trim()) return;

    /**
     * Guard:
     * Only allow asking when document is ready.
     *
     * 保护逻辑：
     * 只有文档 ready 以后才能提问。
     */
    if (selectedDocumentDetail?.status !== "ready") {
      setError("Document is not ready yet.");
      return;
    }

    setError("");
    setIsAsking(true);
    setAnswer("");
    setSources([]);

    try {
      const response = await fetch(
        `${API_BASE_URL}/documents/${selectedDocumentId}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question,
            top_k: 5,
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Ask failed");
      }

      const data: AskResponse = await response.json();

      setAnswer(data.answer);
      setSources(data.sources);
    } catch (err) {
      console.error(err);
      setError("Failed to ask document.");
    } finally {
      setIsAsking(false);
    }
  }

  /**
   * Select document from sidebar.
   * 从左侧文档列表选中文档。
   */
  async function selectDocument(documentId: string) {
    setError("");
    setAnswer("");
    setSources([]);
    setQuestion("");

    setSelectedDocumentId(documentId);

    try {
      await loadDocumentDetail(documentId);
    } catch (err) {
      console.error(err);
      setError("Failed to load document.");
    }
  }

  /**
   * Load document list on first page load.
   * 页面首次加载时，加载文档列表。
   */
  useEffect(() => {
    loadDocuments().catch((err) => {
      console.error(err);
      setError("Failed to load documents.");
    });
  }, []);

  /**
   * Poll selected document status.
   * 轮询当前选中文档的处理状态。
   *
   * Why polling?
   * 为什么要 polling？
   *
   * Day 7 backend uses FastAPI BackgroundTasks.
   * The upload request returns immediately,
   * while ingestion continues in the background.
   *
   * Day 7 后端使用 FastAPI BackgroundTasks。
   * 上传请求会立即返回，但 ingestion 在后台继续执行。
   *
   * Therefore the frontend periodically checks:
   * 所以前端需要定期检查：
   *
   * GET /documents/{document_id}
   *
   * until status becomes:
   * 直到状态变成：
   *
   * ready or failed
   */
  useEffect(() => {
    if (!selectedDocumentId) return;

    const interval = window.setInterval(async () => {
      try {
        const detail = await loadDocumentDetail(selectedDocumentId);
        await loadDocuments();

        /**
         * Stop polling once processing finishes.
         * 当处理完成后停止 polling。
         */
        if (detail.status === "ready" || detail.status === "failed") {
          window.clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    /**
     * Cleanup interval when selectedDocumentId changes
     * or when component unmounts.
     *
     * 当 selectedDocumentId 改变或者组件卸载时，
     * 清理 interval。
     */
    return () => window.clearInterval(interval);
  }, [selectedDocumentId]);

  /**
   * Derived state:
   * Whether user can ask the selected document.
   *
   * 派生状态：
   * 当前是否允许对文档提问。
   */
  const canAsk =
    Boolean(selectedDocumentId) &&
    selectedDocumentDetail?.status === "ready" &&
    Boolean(question.trim()) &&
    !isAsking;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <AppNav />

      <div className="mx-auto max-w-6xl px-6 pb-8">
        {/* Page header / 页面头部 */}
        <header className="mb-8 border-b border-zinc-800 pb-4">
          <h1 className="text-2xl font-semibold">
            Enterprise Document Assistant
          </h1>

          <p className="mt-2 text-sm text-zinc-400">
            Upload a PDF and ask questions using RAG with embeddings, pgvector,
            async ingestion, and citation-aware answers.
          </p>
        </header>

        {/* Error banner / 错误提示 */}
        {error && (
          <div className="mb-4 rounded-xl border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Upload section / 上传区域 */}
        <section className="mb-8 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
          <h2 className="mb-3 text-lg font-semibold">Upload PDF</h2>

          <p className="mb-4 text-sm text-zinc-400">
            After upload, the backend will process the PDF in the background:
            extract text, chunk content, create embeddings, and store vectors in
            pgvector.
          </p>

          <div className="flex flex-col gap-3 md:flex-row">
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => {
                setFile(event.target.files?.[0] || null);
              }}
              className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
            />

            <button
              onClick={uploadDocument}
              disabled={!file || isUploading}
              className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            >
              {isUploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </section>

        {/* Main content grid / 主内容区域 */}
        <section className="grid gap-6 md:grid-cols-[300px_1fr]">
          {/* Document list / 文档列表 */}
          <aside className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <h2 className="mb-3 text-lg font-semibold">Documents</h2>

            {documents.length === 0 ? (
              <div className="rounded-xl border border-zinc-800 p-3 text-sm text-zinc-500">
                No documents uploaded yet.
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((document) => (
                  <button
                    key={document.id}
                    onClick={() => selectDocument(document.id)}
                    className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                      selectedDocumentId === document.id
                        ? "bg-zinc-800 text-white"
                        : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
                    }`}
                  >
                    <div className="truncate font-medium">
                      {document.filename}
                    </div>

                    <div className="mt-1 flex items-center justify-between gap-2 text-xs">
                      <span
                        className={`rounded-full px-2 py-0.5 ${
                          document.status === "ready"
                            ? "bg-green-950 text-green-300"
                            : document.status === "failed"
                              ? "bg-red-950 text-red-300"
                              : "bg-yellow-950 text-yellow-300"
                        }`}
                      >
                        {getStatusLabel(document.status)}
                      </span>

                      <span className="text-zinc-600">
                        {new Date(document.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </aside>

          {/* Ask document panel / 文档问答区域 */}
          <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <h2 className="mb-3 text-lg font-semibold">Ask Document</h2>

            {/* Selected document detail / 当前文档详情 */}
            {selectedDocumentDetail ? (
              <div className="mb-4 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-400">
                <div className="mb-1">
                  <span className="text-zinc-500">File:</span>{" "}
                  {selectedDocumentDetail.filename}
                </div>

                <div className="mb-1">
                  <span className="text-zinc-500">Status:</span>{" "}
                  {getStatusLabel(selectedDocumentDetail.status)}
                </div>

                <div className="mb-1">
                  <span className="text-zinc-500">Chunks:</span>{" "}
                  {selectedDocumentDetail.chunk_count}
                </div>

                <div className="mb-1">
                  <span className="text-zinc-500">Updated:</span>{" "}
                  {formatDate(selectedDocumentDetail.updated_at)}
                </div>

                {/* Processing hint / 处理中提示 */}
                {(selectedDocumentDetail.status === "uploaded" ||
                  selectedDocumentDetail.status === "processing") && (
                  <div className="mt-3 rounded-lg border border-yellow-900 bg-yellow-950/40 px-3 py-2 text-yellow-300">
                    The document is being processed. The page will check status
                    every 2 seconds.
                  </div>
                )}

                {/* Failed status / 失败状态 */}
                {selectedDocumentDetail.status === "failed" && (
                  <div className="mt-3 rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-red-300">
                    <div className="font-semibold">Processing failed</div>
                    {selectedDocumentDetail.error_message && (
                      <div className="mt-1">
                        {selectedDocumentDetail.error_message}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="mb-4 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-500">
                Select or upload a document to start asking questions.
              </div>
            )}

            {/* Question input / 问题输入 */}
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about the selected document..."
              className="mb-3 min-h-28 w-full resize-none rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-blue-500"
            />

            <button
              onClick={askDocument}
              disabled={!canAsk}
              className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            >
              {isAsking ? "Thinking..." : "Ask"}
            </button>

            {/* Why disabled / 禁用原因提示 */}
            {selectedDocumentDetail &&
              selectedDocumentDetail.status !== "ready" && (
                <p className="mt-2 text-xs text-zinc-500">
                  You can ask questions once the document status becomes ready.
                </p>
              )}

            {/* Answer / 答案 */}
            {answer && (
              <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                <h3 className="mb-2 font-semibold">Answer</h3>

                <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-300">
                  {answer}
                </p>
              </div>
            )}

            {/* Sources / 来源引用 */}
            {sources.length > 0 && (
              <div className="mt-6">
                <h3 className="mb-3 font-semibold">Sources</h3>

                <div className="space-y-3">
                  {sources.map((source, index) => (
                    <div
                      key={source.chunk_id}
                      className="rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-400"
                    >
                      <div className="mb-2 text-xs text-zinc-500">
                        Source {index + 1} · {source.filename} · Page{" "}
                        {source.page_number ?? "N/A"} · Chunk{" "}
                        {source.chunk_index}
                      </div>

                      <p className="line-clamp-5 leading-6">{source.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}
