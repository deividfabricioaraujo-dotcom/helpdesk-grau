import { useState, useRef, useEffect } from "react";

import {
  Bot,
  Send,
  User,
  Loader2,
} from "lucide-react";

import { API } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const SUGGESTIONS = {
  public: [
    "Como abro um chamado?",
    "Meu PC não liga, o que faço?",
    "Qual o status do meu chamado GT-...",
  ],

  admin: [
    "Quantos chamados abertos hoje?",
    "Resuma os chamados urgentes",
    "Agrupe as falhas por sala",
  ],
};

let msgSeq = 0;

const makeMsg = (role, text) => ({
  id: `m${msgSeq++}`,
  role,
  text,
});

export const DeividChat = ({
  scope = "public",
  compact = false,
}) => {

  const [messages, setMessages] = useState(() => [
    makeMsg(
      "assistant",
      scope === "admin"
        ? 'Olá! Sou a IA GRAU. Posso resumir e analisar os chamados. Pergunte, por exemplo: "resuma os urgentes".'
        : "Olá! Sou a Unidade Grau Técnico. Posso ajudar com dúvidas e consultar o andamento do seu chamado pelo código."
    ),
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sessionId = useRef(
    `${scope}-${Math.random()
      .toString(36)
      .slice(2)}`
  );

  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  const send = async (text) => {
    const msg = (text ?? input).trim();

    if (!msg || loading) return;

    setInput("");

    setMessages((current) => [
      ...current,
      makeMsg("user", msg),
      makeMsg("assistant", ""),
    ]);

    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          message: msg,
          scope,
          session_id: sessionId.current,
        }),
      });

      if (!res.ok) {
        throw new Error(
          `HTTP ${res.status}`
        );
      }

      const reader = res.body.getReader();

      const decoder = new TextDecoder();

      let acc = "";

      while (true) {

        const {
          done,
          value,
        } = await reader.read();

        if (done) break;

        acc += decoder.decode(
          value,
          {
            stream: true,
          }
        );

        setMessages((current) => {

          const copy = [...current];

          copy[copy.length - 1] = {
            ...copy[copy.length - 1],
            text: acc,
          };

          return copy;
        });
      }

    } catch (error) {

      console.error(
        "Erro na IA:",
        error
      );

      setMessages((current) => {

        const copy = [...current];

        copy[copy.length - 1] = {
          ...copy[copy.length - 1],
          text:
            "Não consegui responder agora. Tente novamente.",
        };

        return copy;
      });

    } finally {

      setLoading(false);

    }
  };

  const suggestions =
    SUGGESTIONS[scope] ||
    SUGGESTIONS.public;

  return (
    <div
      className="flex h-full flex-col"
      data-testid="deivid-chat-panel"
    >

      {/* =================================================
          CABEÇALHO
      ================================================== */}

      <div className="border-b border-emerald-500/10 px-4 py-4">

        <div className="flex items-center gap-3">

          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10">

            <Bot className="h-5 w-5 text-emerald-400" />

          </div>

          <div>

            <div className="text-sm font-semibold text-white">

              {scope === "admin"
                ? "IA GRAU"
                : "Unidade Grau Técnico"}

            </div>

            <div className="text-[10px] text-emerald-500/60">

              Assistente de suporte

            </div>

          </div>

        </div>

      </div>

      {/* =================================================
          MENSAGENS
      ================================================== */}

      <div
        className={`flex-1 space-y-3 overflow-y-auto px-4 py-4 ${
          compact
            ? "max-h-[300px]"
            : ""
        }`}
      >

        {messages.map(
          (message) => (

            <div
              key={message.id}
              className={`flex gap-2 ${
                message.role === "user"
                  ? "justify-end"
                  : "justify-start"
              }`}
            >

              {message.role ===
                "assistant" && (

                <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10">

                  <Bot className="h-4 w-4 text-emerald-400" />

                </div>

              )}

              <div
                className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                  message.role === "user"
                    ? "bg-emerald-500 text-black"
                    : "border border-white/5 bg-white/[0.03] text-gray-300"
                }`}
              >

                {message.text}

              </div>

              {message.role ===
                "user" && (

                <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.05]">

                  <User className="h-4 w-4 text-gray-400" />

                </div>

              )}

            </div>

          )
        )}

        {loading && (

          <div className="flex items-center gap-2 text-xs text-gray-500">

            <Loader2 className="h-4 w-4 animate-spin" />

            IA GRAU está analisando...

          </div>

        )}

        <div ref={endRef} />

      </div>

      {/* =================================================
          SUGESTÕES
      ================================================== */}

      {!input &&
        messages.length <= 1 && (

        <div className="flex flex-wrap gap-2 px-4 pb-3">

          {suggestions.map(
            (suggestion) => (

              <button
                key={suggestion}
                type="button"
                onClick={() =>
                  send(suggestion)
                }
                className="rounded-lg border border-emerald-500/10 bg-emerald-500/[0.03] px-3 py-2 text-left text-[11px] text-gray-400 transition-colors hover:border-emerald-500/20 hover:bg-emerald-500/10 hover:text-emerald-300"
              >
                {suggestion}
              </button>

            )
          )}

        </div>

      )}

      {/* =================================================
          INPUT
      ================================================== */}

      <div className="border-t border-white/5 p-3">

        <form
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
          className="flex items-center gap-2"
        >

          <Input
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            placeholder={
              scope === "admin"
                ? "Pergunte à IA GRAU..."
                : "Digite sua dúvida..."
            }
            disabled={loading}
            className="border-white/10 bg-black/20 text-sm text-white placeholder:text-gray-600 focus-visible:ring-emerald-500"
          />

          <Button
            type="submit"
            size="icon"
            disabled={
              loading ||
              !input.trim()
            }
            className="shrink-0 bg-emerald-500 text-black hover:bg-emerald-400"
          >

            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}

          </Button>

        </form>

      </div>

    </div>
  );
};