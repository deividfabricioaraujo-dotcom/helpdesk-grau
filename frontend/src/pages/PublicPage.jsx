import { useState } from "react";
import { toast } from "sonner";
import { api, formatApiError } from "@/lib/api";
import { DeividChat } from "@/components/DeividChat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Link } from "react-router-dom";
import {
  Monitor,
  Mouse,
  Keyboard,
  Wifi,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Search,
  Loader2,
  Lock,
} from "lucide-react";

const DEVICES = [
  { id: "pc", label: "Computador / PC", icon: Monitor },
  { id: "mouse", label: "Mouse", icon: Mouse },
  { id: "keyboard", label: "Teclado", icon: Keyboard },
  { id: "internet_projector", label: "Internet / Projetor", icon: Wifi },
];

const PRIORITIES = [
  { v: "baixa", l: "Baixa" },
  { v: "media", l: "Média" },
  { v: "alta", l: "Alta" },
  { v: "urgente", l: "Urgente" },
];

const STATUS_LABELS = {
  aberto: "Aberto",
  em_andamento: "Em Andamento",
  resolvido: "Resolvido",
  cancelado: "Cancelado",
};

const emptyForm = {
  requester_name: "",
  building: "",
  floor: "",
  room: "",
  priority: "media",
  talk_to_deivid: false,
  notes: "",
};

export default function PublicPage() {
  const [form, setForm] = useState(emptyForm);

  const [devices, setDevices] = useState({
    pc: "ok",
    mouse: "ok",
    keyboard: "ok",
    internet_projector: "ok",
  });

  const [submitting, setSubmitting] = useState(false);

  const [lookupCode, setLookupCode] = useState("");
  const [lookupResult, setLookupResult] = useState(null);
  const [lookingUp, setLookingUp] = useState(false);

  const set = (k, v) => {
    setForm((f) => ({
      ...f,
      [k]: v,
    }));
  };

  const submit = async (e) => {
    e.preventDefault();

    if (
      !form.requester_name.trim() ||
      !form.building.trim() ||
      !form.room.trim()
    ) {
      toast.error("Preencha nome, prédio e sala para enviar.");
      return;
    }

    setSubmitting(true);

    try {
      const { data } = await api.post("/tickets", {
        ...form,
        devices,
      });

      toast.success(`Chamado aberto! Código: ${data.code}`, {
        description: "Guarde o código para acompanhar o andamento.",
      });

      setForm(emptyForm);

      setDevices({
        pc: "ok",
        mouse: "ok",
        keyboard: "ok",
        internet_projector: "ok",
      });
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const lookup = async () => {
    if (!lookupCode.trim()) return;

    setLookingUp(true);
    setLookupResult(null);

    try {
      const { data } = await api.get(
        `/tickets/public/${lookupCode.trim().toUpperCase()}`
      );

      setLookupResult(data);
    } catch {
      toast.error("Chamado não encontrado. Verifique o código.");
    } finally {
      setLookingUp(false);
    }
  };

  return (
    <div className="min-h-screen bg-background grid-backdrop">
      {/* Header */}
      <header className="glass sticky top-0 z-30 border-b border-emerald-500/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">

          {/* NOVA LOGO */}
          <img
            src="https://i.imgur.com/CSZRDI6.png"
            alt="Grau Técnico TI"
            className="h-10 w-auto max-w-[180px] object-contain"
          />

          <Link
            to="/admin/login"
            data-testid="link-admin-login"
            className="flex items-center gap-1.5 rounded-lg border border-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/10"
          >
            <Lock className="h-3.5 w-3.5" />
            Área Técnica
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-4 pt-10 sm:px-6">
        <div className="animate-fade-up">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 font-mono-tech text-[11px] uppercase tracking-widest text-emerald-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            Central de Suporte de TI
          </span>

          <h1 className="mt-4 font-display text-3xl font-extrabold tracking-tight text-emerald-50 sm:text-4xl lg:text-5xl">
            Abra seu chamado em segundos
          </h1>

          <p className="mt-3 max-w-xl text-sm leading-relaxed text-gray-400 sm:text-base">
            Identifique-se, descreva o problema e acompanhe o atendimento.
            Sem burocracia — direto com a equipe técnica.
          </p>
        </div>
      </section>

      {/* Content grid */}
      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-12">

        {/* Form */}
        <form
          onSubmit={submit}
          data-testid="public-ticket-form"
          className="animate-fade-up rounded-2xl border border-emerald-500/15 bg-[#141F18]/60 p-5 sm:p-7 lg:col-span-7"
        >
          <h2 className="font-display text-xl font-bold text-emerald-100">
            Novo chamado
          </h2>

          {/* Identity */}
          <div className="mt-5 grid gap-4 sm:grid-cols-2">

            <div className="sm:col-span-2">
              <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
                Nome completo *
              </Label>

              <Input
                data-testid="input-requester-name"
                value={form.requester_name}
                onChange={(e) =>
                  set("requester_name", e.target.value)
                }
                placeholder="Seu nome"
                className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
              />
            </div>

            <div>
              <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
                Prédio / Bloco *
              </Label>

              <Input
                data-testid="input-building"
                value={form.building}
                onChange={(e) =>
                  set("building", e.target.value)
                }
                placeholder="Ex.: Bloco A"
                className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">

              <div>
                <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
                  Andar
                </Label>

                <Input
                  data-testid="input-floor"
                  value={form.floor}
                  onChange={(e) =>
                    set("floor", e.target.value)
                  }
                  placeholder="Ex.: 2º"
                  className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
                />
              </div>

              <div>
                <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
                  Sala *
                </Label>

                <Input
                  data-testid="input-room"
                  value={form.room}
                  onChange={(e) =>
                    set("room", e.target.value)
                  }
                  placeholder="Ex.: Lab 03"
                  className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
                />
              </div>

            </div>
          </div>

          {/* Devices */}
          <div className="mt-6">

            <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
              Status dos equipamentos
            </Label>

            <div className="mt-2 grid gap-2.5 sm:grid-cols-2">

              {DEVICES.map(({ id, label, icon: Icon }) => {
                const problem = devices[id] === "problem";

                return (
                  <div
                    key={id}
                    className="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/15 bg-black/20 px-3 py-2.5"
                  >

                    <div className="flex items-center gap-2 text-sm text-gray-200">
                      <Icon
                        className={`h-4 w-4 ${
                          problem
                            ? "text-red-400"
                            : "text-emerald-400"
                        }`}
                      />

                      {label}
                    </div>

                    <div className="flex overflow-hidden rounded-lg border border-emerald-500/20">

                      <button
                        type="button"
                        data-testid={`device-${id}-ok`}
                        onClick={() =>
                          setDevices((d) => ({
                            ...d,
                            [id]: "ok",
                          }))
                        }
                        className={`px-2 py-1 text-xs transition-colors ${
                          !problem
                            ? "bg-emerald-500 text-black"
                            : "text-emerald-400/70 hover:bg-emerald-500/10"
                        }`}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                      </button>

                      <button
                        type="button"
                        data-testid={`device-${id}-problem`}
                        onClick={() =>
                          setDevices((d) => ({
                            ...d,
                            [id]: "problem",
                          }))
                        }
                        className={`px-2 py-1 text-xs transition-colors ${
                          problem
                            ? "bg-red-500 text-white"
                            : "text-red-400/70 hover:bg-red-500/10"
                        }`}
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                      </button>

                    </div>
                  </div>
                );
              })}

            </div>

            <p className="mt-1.5 font-mono-tech text-[10px] text-emerald-500/50">
              Verde = funcionando • Vermelho = com defeito
            </p>
          </div>

          {/* Priority + notes */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2">

            <div>
              <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
                Prioridade
              </Label>

              <Select
                value={form.priority}
                onValueChange={(v) =>
                  set("priority", v)
                }
              >
                <SelectTrigger
                  data-testid="select-priority"
                  className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 focus:ring-emerald-500"
                >
                  <SelectValue />
                </SelectTrigger>

                <SelectContent className="border-emerald-500/20 bg-[#141F18] text-emerald-50">

                  {PRIORITIES.map((p) => (
                    <SelectItem
                      key={p.v}
                      value={p.v}
                      data-testid={`priority-opt-${p.v}`}
                    >
                      {p.l}
                    </SelectItem>
                  ))}

                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end">

              <label className="flex w-full cursor-pointer items-center gap-3 rounded-xl border border-emerald-500/15 bg-black/20 px-3 py-2.5">

                <Checkbox
                  data-testid="checkbox-talk-deivid"
                  checked={form.talk_to_deivid}
                  onCheckedChange={(v) =>
                    set("talk_to_deivid", !!v)
                  }
                  className="border-emerald-500/40 data-[state=checked]:bg-emerald-500 data-[state=checked]:text-black"
                />

                <span className="text-sm text-gray-200">
                  Quero falar direto com o Deivid
                </span>

              </label>
            </div>
          </div>

          {/* Notes */}
          <div className="mt-4">

            <Label className="text-xs uppercase tracking-wider text-emerald-400/80">
              Observações
            </Label>

            <Textarea
              data-testid="input-notes"
              value={form.notes}
              onChange={(e) =>
                set("notes", e.target.value)
              }
              placeholder="Descreva o problema com detalhes…"
              rows={3}
              className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
            />

          </div>

          {/* Submit */}
          <Button
            type="submit"
            data-testid="btn-submit-ticket"
            disabled={submitting}
            className="mt-6 w-full bg-emerald-500 text-base font-semibold text-black hover:bg-emerald-400"
          >
            {submitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}

            Enviar chamado
          </Button>

        </form>

        {/* Sidebar */}
        <div className="animate-fade-up space-y-6 lg:col-span-5">

          {/* Lookup */}
          <div className="rounded-2xl border border-emerald-500/15 bg-[#141F18]/60 p-5">

            <h3 className="font-display text-sm font-bold text-emerald-100">
              Acompanhar chamado
            </h3>

            <p className="mt-1 text-xs text-gray-400">
              Digite o código (ex.: GT-A1B2C3).
            </p>

            <div className="mt-3 flex gap-2">

              <Input
                data-testid="input-lookup-code"
                value={lookupCode}
                onChange={(e) =>
                  setLookupCode(e.target.value)
                }
                onKeyDown={(e) =>
                  e.key === "Enter" && lookup()
                }
                placeholder="GT-..."
                className="border-emerald-500/20 bg-black/30 font-mono-tech text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
              />

              <Button
                data-testid="btn-lookup"
                onClick={lookup}
                disabled={lookingUp}
                variant="outline"
                className="border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10"
              >
                {lookingUp ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
              </Button>

            </div>

            {lookupResult && (
              <div
                data-testid="lookup-result"
                className="mt-3 rounded-xl border border-emerald-500/20 bg-black/30 p-3 text-sm"
              >

                <div className="flex items-center justify-between">

                  <span className="font-mono-tech text-emerald-300">
                    {lookupResult.code}
                  </span>

                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">
                    {STATUS_LABELS[lookupResult.status]}
                  </span>

                </div>

                <p className="mt-1 text-xs text-gray-400">
                  {lookupResult.building} • Sala {lookupResult.room}
                </p>

              </div>
            )}

          </div>

          {/* Assistente */}
          <div className="overflow-hidden rounded-2xl border border-emerald-500/15 bg-[#141F18]/60">
            <DeividChat
              scope="public"
              compact
            />
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-emerald-500/10 py-6 text-center font-mono-tech text-[11px] uppercase tracking-widest text-emerald-500/40">
        grau Técnico — Sistema de Chamados
      </footer>
    </div>
  );
}