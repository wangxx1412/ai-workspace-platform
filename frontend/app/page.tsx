"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import AppNav from "./components/AppNav";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type MessageRole = "user" | "assistant";

type Message = {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
};

type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type ConversationDetailResponse = {
  id: string;
  title: string;
  messages: {
    id: string;
    role: MessageRole;
    content: string;
    created_at: string;
  }[];
};

type DocumentDetail = {
  id: string;
  filename: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
};

const INITIAL_MESSAGES: Message[] = [
  {
    id: "initial-assistant-message",
    role: "assistant",
    content: "Hi, I am your AI workspace assistant. Ask me anything.",
    createdAt: 0,
  },
];

function createMessage(role: MessageRole, content: string): Message {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: Date.now(),
  };
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [selectedDocumentDetail, setSelectedDocumentDetail] =
    useState<DocumentDetail | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  async function loadConversations() {
    const response = await fetch(`${API_BASE_URL}/conversations`);

    if (!response.ok) {
      throw new Error("Failed to load conversations");
    }

    const data: Conversation[] = await response.json();
    setConversations(data);
  }

  async function createConversation() {
    if (isStreaming) return;

    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/conversations`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to create conversation");
      }

      const conversation: Conversation = await response.json();

      setActiveConversationId(conversation.id);
      setMessages(INITIAL_MESSAGES);
      setInput("");

      await loadConversations();
    } catch (err) {
      console.error(err);
      setError("Failed to create a new conversation.");
    }
  }

  async function loadConversation(conversationId: string) {
    if (isStreaming) return;

    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/${conversationId}`,
      );

      if (!response.ok) {
        throw new Error("Failed to load conversation");
      }

      const data: ConversationDetailResponse = await response.json();

      setActiveConversationId(data.id);

      if (data.messages.length === 0) {
        setMessages(INITIAL_MESSAGES);
      } else {
        setMessages(
          data.messages.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            createdAt: new Date(message.created_at).getTime(),
          })),
        );
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load conversation.");
    }
  }

  async function ensureConversation(): Promise<string> {
    if (activeConversationId) {
      return activeConversationId;
    }

    const response = await fetch(`${API_BASE_URL}/conversations`, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error("Failed to create conversation");
    }

    const conversation: Conversation = await response.json();

    setActiveConversationId(conversation.id);
    await loadConversations();

    return conversation.id;
  }

  async function sendMessage(customMessages?: Message[]) {
    const isRetry = Boolean(customMessages);
    const trimmed = input.trim();

    if (!isRetry && (!trimmed || isStreaming)) return;
    if (isRetry && isStreaming) return;

    setError("");

    let nextMessages: Message[];

    if (customMessages) {
      nextMessages = customMessages;
    } else {
      const userMessage = createMessage("user", trimmed);
      const assistantMessage = createMessage("assistant", "");

      nextMessages = [...messages, userMessage, assistantMessage];

      setMessages(nextMessages);
      setInput("");
    }

    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const conversationId = await ensureConversation();

      const requestMessages = nextMessages
        .filter((message) => message.content.trim().length > 0)
        .map((message) => ({
          role: message.role,
          content: message.content,
        }));

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          conversation_id: conversationId,
          messages: requestMessages,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body received");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;

          if (lastIndex < 0) return updated;

          updated[lastIndex] = {
            ...updated[lastIndex],
            content: updated[lastIndex].content + chunk,
          };

          return updated;
        });
      }

      await loadConversations();
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;

          if (
            updated[lastIndex]?.role === "assistant" &&
            updated[lastIndex].content.trim().length === 0
          ) {
            updated[lastIndex] = {
              ...updated[lastIndex],
              content: "[Generation stopped]",
            };
          }

          return updated;
        });

        return;
      }

      console.error(err);

      setError("Something went wrong. Please check backend logs.");

      setMessages((prev) => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;

        if (updated[lastIndex]?.role === "assistant") {
          updated[lastIndex] = {
            ...updated[lastIndex],
            content:
              "Sorry, something went wrong while generating the response.",
          };
        }

        return updated;
      });
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  async function loadDocumentDetail(documentId: string) {
    const response = await fetch(`${API_BASE_URL}/documents/${documentId}`);

    if (!response.ok) {
      throw new Error("Failed to load document detail");
    }

    const data: DocumentDetail = await response.json();
    setSelectedDocumentDetail(data);

    return data;
  }

  function stopGenerating() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }

  function retryLastMessage() {
    if (isStreaming) return;

    const reversedLastUserIndex = [...messages]
      .reverse()
      .findIndex((message) => message.role === "user");

    if (reversedLastUserIndex === -1) return;

    const actualLastUserIndex = messages.length - 1 - reversedLastUserIndex;

    const messagesBeforeRetry = messages.slice(0, actualLastUserIndex + 1);
    const newAssistantMessage = createMessage("assistant", "");

    const retryMessages = [...messagesBeforeRetry, newAssistantMessage];

    setMessages(retryMessages);
    sendMessage(retryMessages);
  }

  function clearCurrentView() {
    if (isStreaming) return;

    setMessages(INITIAL_MESSAGES);
    setActiveConversationId(null);
    setInput("");
    setError("");
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  useEffect(() => {
    loadConversations().catch((err) => {
      console.error(err);
      setError("Failed to load conversations.");
    });
  }, []);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <AppNav />
      <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-6xl overflow-hidden rounded-2xl border border-zinc-800">
        <aside className="flex w-72 flex-col border-r border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-4">
            <h2 className="mb-3 text-lg font-semibold">AI Workspace</h2>
            <button
              onClick={createConversation}
              disabled={isStreaming}
              className="w-full rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            >
              New Chat
            </button>
          </div>

          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Conversations
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="rounded-xl border border-zinc-800 p-3 text-sm text-zinc-500">
                No conversations yet.
              </div>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  onClick={() => loadConversation(conversation.id)}
                  disabled={isStreaming}
                  className={`w-full truncate rounded-xl px-3 py-2 text-left text-sm transition ${
                    activeConversationId === conversation.id
                      ? "bg-zinc-800 text-white"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                  title={conversation.title}
                >
                  {conversation.title}
                </button>
              ))
            )}
          </div>

          <button
            onClick={clearCurrentView}
            disabled={isStreaming}
            className="mt-4 rounded-xl border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Clear View
          </button>
        </aside>

        <section className="flex min-h-screen flex-1 flex-col px-4 py-6">
          <header className="mb-6 flex items-start justify-between gap-4 border-b border-zinc-800 pb-4">
            <div>
              <h1 className="text-2xl font-semibold">AI Workspace Platform</h1>
              <p className="mt-1 text-sm text-zinc-400">
                Streaming AI chat with persistent conversations, markdown
                rendering, retry, and stop generation.
              </p>
            </div>

            <div className="rounded-xl border border-zinc-800 px-3 py-2 text-xs text-zinc-500">
              {activeConversationId
                ? `Conversation: ${activeConversationId.slice(0, 8)}...`
                : "No active conversation"}
            </div>
          </header>

          <div className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <article
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                    message.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-zinc-800 text-zinc-100"
                  }`}
                >
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide opacity-70">
                    {message.role === "user" ? "You" : "Assistant"}
                  </div>

                  <div className="max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeHighlight]}
                      components={{
                        h1: ({ children }) => (
                          <h1 className="mb-3 mt-4 text-xl font-bold">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="mb-2 mt-4 text-lg font-semibold">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="mb-2 mt-3 text-base font-semibold">
                            {children}
                          </h3>
                        ),
                        p: ({ children }) => (
                          <p className="mb-2 leading-6">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="mb-3 ml-5 list-disc space-y-1">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="mb-3 ml-5 list-decimal space-y-1">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="leading-6">{children}</li>
                        ),
                        table: ({ children }) => (
                          <div className="my-4 overflow-x-auto">
                            <table className="w-full border-collapse border border-zinc-700 text-sm">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-zinc-700">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="border border-zinc-700 px-3 py-2 text-left font-semibold">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-zinc-700 px-3 py-2 align-top">
                            {children}
                          </td>
                        ),
                        code: ({ children }) => (
                          <code className="rounded bg-zinc-950 px-1 py-0.5 text-sm">
                            {children}
                          </code>
                        ),
                        pre: ({ children }) => (
                          <pre className="my-3 overflow-x-auto rounded-xl bg-zinc-950 p-4 text-sm">
                            {children}
                          </pre>
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </article>
              </div>
            ))}

            {isStreaming && (
              <div className="text-sm text-zinc-500">
                Assistant is typing...
              </div>
            )}
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <footer className="mt-4 space-y-3">
            <textarea
              className="min-h-28 w-full resize-none rounded-2xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 outline-none focus:border-blue-500"
              placeholder="Ask something..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
            />

            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-zinc-500">
                Enter to send · Shift + Enter for new line
              </div>

              <div className="flex gap-3">
                <button
                  onClick={retryLastMessage}
                  disabled={
                    isStreaming ||
                    !messages.some((message) => message.role === "user")
                  }
                  className="rounded-xl border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Retry
                </button>

                {isStreaming ? (
                  <button
                    onClick={stopGenerating}
                    className="rounded-xl bg-red-600 px-5 py-2 text-sm font-semibold text-white hover:bg-red-500"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => sendMessage()}
                    disabled={!input.trim()}
                    className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
                  >
                    Send
                  </button>
                )}
              </div>
            </div>
          </footer>
        </section>
      </div>
    </main>
  );
}
