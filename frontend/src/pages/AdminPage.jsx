import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  Archive,
  ArchiveRestore,
  CheckCircle2,
  Clock3,
  History,
  LogOut,
  MessageSquare,
  RefreshCw,
  Search,
  Server,
  XCircle,
} from "lucide-react";

import { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { DeividChat } from "@/components/DeividChat";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const STATUS_OPTIONS = [
  { value: "aberto", label: "Aberto" },
  { value: "em_atendimento", label: "Em atendimento" },
  { value: "resolvido", label: "Resolvido" },
  { value: "cancelado", label: "Cancelado" },
];

const PRIORITY_OPTIONS = [
  { value: "baixa", label: "Baixa" },
  { value: "media", label: "Média" },
  { value: "alta", label: "Alta" },
  { value: "urgente", label: "Urgente" },
];

const BUILDING_OPTIONS = [
  { value: "predio_1", label: "Prédio 1" },
  { value: "predio_2", label: "Prédio 2" },
  { value: "predio_3", label: "Prédio 3" },
];

const getStatusLabel = (status) => {
  const found = STATUS_OPTIONS.find((item) => item.value === status);
  return found?.label || status || "Aberto";
};

const getPriorityLabel = (priority) => {
  const found = PRIORITY_OPTIONS.find((item) => item.value === priority);
  return found?.label || priority || "Média";
};

const getBuildingLabel = (building) => {
  const found = BUILDING_OPTIONS.find((item) => item.value === building);
  return found?.label || building || "Não informado";
};

const statusClass = (status) => {
  switch (status) {
    case "resolvido":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";

    case "em_atendimento":
      return "border-blue-500/30 bg-blue-500/10 text-blue-300";

    case "cancelado":
      return "border-red-500/30 bg-red-500/10 text-red-300";

    default:
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }
};

const priorityClass = (priority) => {
  switch (priority) {
    case "urgente":
      return "border-red-500/30 bg-red-500/10 text-red-300";

    case "alta":
      return "border-orange-500/30 bg-orange-500/10 text-orange-300";

    case "baixa":
      return "border-slate-500/30 bg-slate-500/10 text-slate-300";

    default:
      return "border-yellow-500/30 bg-yellow-500/10 text-yellow-300";
  }
};

const formatDate = (value) => {
  if (!value) return "—";

  try {
    return new Date(value).toLocaleString("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
};

export default function AdminPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  const [archived, setArchived] = useState(false);
  const [search, setSearch] = useState("");

  const [fBuilding, setFBuilding] = useState("all");
  const [fPriority, setFPriority] = useState("all");
  const [fStatus, setFStatus] = useState("all");

  const [auditTicket, setAuditTicket] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const mountedRef = useRef(false);
  const loadRef = useRef(null);

  /*
   * ---------------------------------------------------------
   * MOUNT
   * ---------------------------------------------------------
   */

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  /*
   * ---------------------------------------------------------
   * STATS
   * ---------------------------------------------------------
   */

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/tickets/stats`, {
        credentials: "include",
      });

      if (!res.ok) return;

      const data = await res.json();

      if (mountedRef.current) {
        setStats(data || {});
      }
    } catch (error) {
      console.error("Erro ao carregar estatísticas:", error);
    }
  }, []);

  /*
   * ---------------------------------------------------------
   * LOAD TICKETS
   * ---------------------------------------------------------
   */

  const load = useCallback(
    async (silent = false) => {
      try {
        if (!silent && mountedRef.current) {
          setLoading(true);
        }

        const params = new URLSearchParams();

        params.set("archived", archived ? "true" : "false");

        if (search.trim()) {
          params.set("search", search.trim());
        }

        if (fBuilding !== "all") {
          params.set("building", fBuilding);
        }

        if (fPriority !== "all") {
          params.set("priority", fPriority);
        }

        if (fStatus !== "all") {
          params.set("status", fStatus);
        }

        const query = params.toString();

        const res = await fetch(
          `${API}/tickets${query ? `?${query}` : ""}`,
          {
            credentials: "include",
          }
        );

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        if (mountedRef.current) {
          setTickets(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error("Erro ao carregar chamados:", error);

        if (!silent && mountedRef.current) {
          toast.error("Não foi possível carregar os chamados.");
        }
      } finally {
        if (!silent && mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [
      archived,
      search,
      fBuilding,
      fPriority,
      fStatus,
    ]
  );

  useEffect(() => {
    loadRef.current = load;
  }, [load]);

  /*
   * ---------------------------------------------------------
   * LOAD INICIAL / FILTROS
   * ---------------------------------------------------------
   */

  useEffect(() => {
    load(false);
    loadStats();
  }, [load, loadStats]);

  /*
   * ---------------------------------------------------------
   * WEBSOCKET
   * ---------------------------------------------------------
   *
   * Continua funcionando em segundo plano.
   * Não existe nenhum indicador visual de "Tempo real".
   * ---------------------------------------------------------
   */

  useEffect(() => {
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;

      try {
        if (socketRef.current) {
          try {
            socketRef.current.close();
          } catch {}
        }

        const backendUrl =
          process.env.REACT_APP_BACKEND_URL ||
          "http://localhost:8000";

        const wsUrl = backendUrl
          .replace(/^https:\/\//i, "wss://")
          .replace(/^http:\/\//i, "ws://");

        const socket = new WebSocket(
          `${wsUrl}/api/ws/tickets`
        );

        socketRef.current = socket;

        socket.onopen = () => {
          if (destroyed) return;

          console.log("[WEBSOCKET] Conectado.");

          loadRef.current?.(true);
          loadStats();
        };

        socket.onmessage = (event) => {
          if (destroyed) return;

          try {
            const message = JSON.parse(event.data);
            const ticket = message?.ticket;

            if (
              message?.type !== "ticket_created" &&
              message?.type !== "ticket_updated" &&
              message?.type !== "ticket_archived" &&
              message?.type !== "tickets_changed"
            ) {
              return;
            }

            if (ticket?.id) {
              setTickets((current) => {
                const existingIndex = current.findIndex(
                  (item) => item.id === ticket.id
                );

                /*
                 * CHAMADO CRIADO
                 */

                if (message.type === "ticket_created") {
                  if (existingIndex !== -1) {
                    const copy = [...current];
                    copy[existingIndex] = ticket;
                    return copy;
                  }

                  if (!archived) {
                    return [ticket, ...current];
                  }

                  return current;
                }

                /*
                 * CHAMADO ARQUIVADO / RESTAURADO
                 */

                if (message.type === "ticket_archived") {
                  const shouldBeVisible =
                    Boolean(ticket.archived) ===
                    Boolean(archived);

                  if (!shouldBeVisible) {
                    return current.filter(
                      (item) => item.id !== ticket.id
                    );
                  }

                  if (existingIndex !== -1) {
                    const copy = [...current];
                    copy[existingIndex] = ticket;
                    return copy;
                  }

                  return [ticket, ...current];
                }

                /*
                 * CHAMADO ATUALIZADO
                 */

                if (existingIndex !== -1) {
                  const copy = [...current];
                  copy[existingIndex] = ticket;
                  return copy;
                }

                return current;
              });

              if (
                search.trim() ||
                fBuilding !== "all" ||
                fPriority !== "all" ||
                fStatus !== "all"
              ) {
                loadRef.current?.(true);
              }
            } else {
              loadRef.current?.(true);
            }

            loadStats();
          } catch (error) {
            console.error(
              "[WEBSOCKET] Mensagem inválida:",
              error
            );
          }
        };

        socket.onerror = (error) => {
          console.error(
            "[WEBSOCKET] Erro:",
            error
          );
        };

        socket.onclose = () => {
          if (destroyed) return;

          console.log(
            "[WEBSOCKET] Desconectado. Reconectando..."
          );

          if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
          }

          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, 3000);
        };
      } catch (error) {
        console.error(
          "[WEBSOCKET] Falha na conexão:",
          error
        );

        if (!destroyed) {
          reconnectTimerRef.current = setTimeout(
            connect,
            3000
          );
        }
      }
    };

    connect();

    return () => {
      destroyed = true;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (socketRef.current) {
        try {
          socketRef.current.close();
        } catch {}

        socketRef.current = null;
      }
    };
  }, [
    archived,
    search,
    fBuilding,
    fPriority,
    fStatus,
    loadStats,
  ]);

  /*
   * ---------------------------------------------------------
   * STATUS
   * ---------------------------------------------------------
   */

  const changeStatus = async (ticketId, status) => {
    try {
      const res = await fetch(
        `${API}/tickets/${ticketId}/status`,
        {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status }),
        }
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const updatedTicket = await res.json();

      setTickets((current) =>
        current.map((ticket) =>
          ticket.id === ticketId
            ? {
                ...ticket,
                ...updatedTicket,
                status,
              }
            : ticket
        )
      );

      await loadStats();

      toast.success("Status atualizado.");
    } catch (error) {
      console.error(
        "Erro ao alterar status:",
        error
      );

      toast.error(
        "Não foi possível alterar o status."
      );
    }
  };

  /*
   * ---------------------------------------------------------
   * ARQUIVAR / DESARQUIVAR
   * ---------------------------------------------------------
   */

  const toggleArchive = async (ticket) => {
    try {
      const newArchived = !Boolean(ticket.archived);

      const res = await fetch(
        `${API}/tickets/${ticket.id}/archive`,
        {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            archived: newArchived,
          }),
        }
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const updatedTicket = await res.json();

      if (
        Boolean(updatedTicket.archived) !==
        Boolean(archived)
      ) {
        setTickets((current) =>
          current.filter(
            (item) => item.id !== ticket.id
          )
        );
      } else {
        setTickets((current) =>
          current.map((item) =>
            item.id === ticket.id
              ? {
                  ...item,
                  ...updatedTicket,
                  archived: newArchived,
                }
              : item
          )
        );
      }

      await loadStats();

      toast.success(
        newArchived
          ? "Chamado arquivado."
          : "Chamado restaurado."
      );
    } catch (error) {
      console.error(
        "Erro ao arquivar/desarquivar:",
        error
      );

      toast.error(
        "Não foi possível alterar o arquivamento."
      );
    }
  };

  /*
   * ---------------------------------------------------------
   * LOGOUT
   * ---------------------------------------------------------
   */

  const doLogout = async () => {
    try {
      await logout();
    } finally {
      navigate("/login");
    }
  };

  /*
   * ---------------------------------------------------------
   * REFRESH
   * ---------------------------------------------------------
   */

  const refresh = async () => {
    await Promise.all([
      load(false),
      loadStats(),
    ]);
  };

  /*
   * ---------------------------------------------------------
   * KPI
   * ---------------------------------------------------------
   */

  const total =
    stats?.total ??
    stats?.total_tickets ??
    tickets.length ??
    0;

  const open =
    stats?.open ??
    stats?.abertos ??
    stats?.opened ??
    0;

  const inProgress =
    stats?.in_progress ??
    stats?.em_atendimento ??
    stats?.emAtendimento ??
    0;

  const resolved =
    stats?.resolved ??
    stats?.resolvidos ??
    0;

  const urgent =
    stats?.urgent ??
    stats?.urgentes ??
    0;

  return (
    <div className="min-h-screen bg-[#050807] text-white">

      {/* =====================================================
          HEADER
      ====================================================== */}

      <header className="sticky top-0 z-40 border-b border-emerald-500/10 bg-[#050807]/95 backdrop-blur-xl">

        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-4 md:px-6">

          <div className="flex items-center gap-3">

            {/* LOGO GRAU TÉCNICO TI */}
            <img
              src="https://i.imgur.com/9xYp8FB.png"
              alt="Grau Técnico TI"
              className="h-10 w-auto max-w-[180px] object-contain"
            />

            <div className="hidden sm:block">
              <div className="font-display text-sm font-bold text-white">
                Central de Suporte
              </div>

              <div className="font-mono-tech text-[10px] uppercase tracking-widest text-emerald-500/60">
                Painel administrativo
              </div>
            </div>

          </div>

          <div className="flex items-center gap-2">

            {/* =================================================
                IA GRAU
            ================================================== */}

            <Sheet>

              <SheetTrigger asChild>

                <Button
                  variant="outline"
                  size="sm"
                  className="border-emerald-500/20 bg-transparent text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200"
                >
                  <MessageSquare className="mr-2 h-4 w-4" />
                  IA GRAU
                </Button>

              </SheetTrigger>

              <SheetContent
                side="right"
                className="w-full border-emerald-500/10 bg-[#070b09] p-0 sm:max-w-md"
              >

                <SheetHeader className="sr-only">
                  <SheetTitle>
                    IA GRAU
                  </SheetTitle>
                </SheetHeader>

                <DeividChat
                  scope="admin"
                  compact
                />

              </SheetContent>

            </Sheet>

            {/* USUÁRIO */}

            <div className="hidden text-right md:block">

              <div className="text-xs font-semibold text-white">
                {user?.name ||
                  user?.username ||
                  "Administrador"}
              </div>

              <div className="text-[10px] text-emerald-500/60">
                Administrador
              </div>

            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={doLogout}
              className="text-gray-400 hover:bg-red-500/10 hover:text-red-300"
              title="Sair"
            >
              <LogOut className="h-4 w-4" />
            </Button>

          </div>

        </div>

      </header>

      {/* =====================================================
          CONTEÚDO
      ====================================================== */}

      <main className="mx-auto max-w-[1600px] px-4 py-6 md:px-6">

        {/* TÍTULO */}

        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">

          <div>

            <div className="mb-2 flex items-center gap-2">

              <Server className="h-4 w-4 text-emerald-400" />

              <span className="font-mono-tech text-[10px] uppercase tracking-[0.2em] text-emerald-500/60">
                IT • GRAU TÉCNICO
              </span>

            </div>

            <h1 className="font-display text-2xl font-bold tracking-tight text-white md:text-3xl">
              Chamados de suporte
            </h1>

            <p className="mt-1 text-sm text-gray-500">
              Acompanhe e gerencie os chamados.
            </p>

          </div>

          <Button
            onClick={refresh}
            variant="outline"
            className="w-fit border-white/10 bg-white/[0.02] text-gray-300 hover:bg-white/[0.05] hover:text-white"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar
          </Button>

        </div>

        {/* ===================================================
            KPIs
        ==================================================== */}

        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">

          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">

            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Total
              </span>

              <MessageSquare className="h-4 w-4 text-gray-500" />
            </div>

            <div className="font-display text-2xl font-bold">
              {total}
            </div>

          </div>

          <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] p-4">

            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Abertos
              </span>

              <Clock3 className="h-4 w-4 text-amber-400" />
            </div>

            <div className="font-display text-2xl font-bold text-amber-300">
              {open}
            </div>

          </div>

          <div className="rounded-xl border border-blue-500/10 bg-blue-500/[0.03] p-4">

            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Atendimento
              </span>

              <RefreshCw className="h-4 w-4 text-blue-400" />
            </div>

            <div className="font-display text-2xl font-bold text-blue-300">
              {inProgress}
            </div>

          </div>

          <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.03] p-4">

            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Resolvidos
              </span>

              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>

            <div className="font-display text-2xl font-bold text-emerald-300">
              {resolved}
            </div>

          </div>

          <div className="col-span-2 rounded-xl border border-red-500/10 bg-red-500/[0.03] p-4 md:col-span-1">

            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Urgentes
              </span>

              <XCircle className="h-4 w-4 text-red-400" />
            </div>

            <div className="font-display text-2xl font-bold text-red-300">
              {urgent}
            </div>

          </div>

        </div>

        {/* ===================================================
            FILTROS
        ==================================================== */}

        <div className="mb-5 rounded-xl border border-white/5 bg-white/[0.02] p-3">

          <div className="flex flex-col gap-3 xl:flex-row">

            <div className="relative min-w-0 flex-1">

              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />

              <Input
                value={search}
                onChange={(e) =>
                  setSearch(e.target.value)
                }
                placeholder="Buscar chamado..."
                className="border-white/10 bg-black/20 pl-9 text-sm text-white placeholder:text-gray-600 focus-visible:ring-emerald-500"
              />

            </div>

            <Select
              value={fBuilding}
              onValueChange={setFBuilding}
            >

              <SelectTrigger className="w-full border-white/10 bg-black/20 text-gray-300 xl:w-[170px]">
                <SelectValue placeholder="Prédio" />
              </SelectTrigger>

              <SelectContent>

                <SelectItem value="all">
                  Todos os prédios
                </SelectItem>

                {BUILDING_OPTIONS.map((item) => (
                  <SelectItem
                    key={item.value}
                    value={item.value}
                  >
                    {item.label}
                  </SelectItem>
                ))}

              </SelectContent>

            </Select>

            <Select
              value={fPriority}
              onValueChange={setFPriority}
            >

              <SelectTrigger className="w-full border-white/10 bg-black/20 text-gray-300 xl:w-[160px]">
                <SelectValue placeholder="Prioridade" />
              </SelectTrigger>

              <SelectContent>

                <SelectItem value="all">
                  Todas prioridades
                </SelectItem>

                {PRIORITY_OPTIONS.map((item) => (
                  <SelectItem
                    key={item.value}
                    value={item.value}
                  >
                    {item.label}
                  </SelectItem>
                ))}

              </SelectContent>

            </Select>

            <Select
              value={fStatus}
              onValueChange={setFStatus}
            >

              <SelectTrigger className="w-full border-white/10 bg-black/20 text-gray-300 xl:w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>

              <SelectContent>

                <SelectItem value="all">
                  Todos os status
                </SelectItem>

                {STATUS_OPTIONS.map((item) => (
                  <SelectItem
                    key={item.value}
                    value={item.value}
                  >
                    {item.label}
                  </SelectItem>
                ))}

              </SelectContent>

            </Select>

            <Button
              variant="outline"
              onClick={() =>
                setArchived((value) => !value)
              }
              className={`border-white/10 ${
                archived
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "bg-black/20 text-gray-400"
              }`}
            >

              {archived ? (
                <ArchiveRestore className="mr-2 h-4 w-4" />
              ) : (
                <Archive className="mr-2 h-4 w-4" />
              )}

              {archived
                ? "Arquivados"
                : "Ativos"}

            </Button>

          </div>

        </div>

        {/* ===================================================
            LISTA
        ==================================================== */}

        <div className="overflow-hidden rounded-xl border border-white/5 bg-white/[0.02]">

          <div className="border-b border-white/5 px-4 py-3">

            <div className="text-sm font-semibold text-white">

              {archived
                ? "Chamados arquivados"
                : "Chamados ativos"}

            </div>

            <div className="text-[11px] text-gray-600">

              {tickets.length} chamado
              {tickets.length === 1 ? "" : "s"}

            </div>

          </div>

          {loading ? (

            <div className="flex min-h-[300px] items-center justify-center">

              <div className="flex flex-col items-center gap-3">

                <RefreshCw className="h-6 w-6 animate-spin text-emerald-400" />

                <span className="text-xs text-gray-600">
                  Carregando chamados...
                </span>

              </div>

            </div>

          ) : tickets.length === 0 ? (

            <div className="flex min-h-[300px] flex-col items-center justify-center px-6 text-center">

              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.03]">

                <MessageSquare className="h-5 w-5 text-gray-600" />

              </div>

              <div className="text-sm font-semibold text-gray-400">
                Nenhum chamado encontrado
              </div>

              <div className="mt-1 text-xs text-gray-600">
                Tente alterar os filtros ou aguarde novos chamados.
              </div>

            </div>

          ) : (

            <div className="divide-y divide-white/5">

              {tickets.map((ticket) => (

                <div
                  key={ticket.id}
                  className="group flex flex-col gap-4 px-4 py-4 transition-colors hover:bg-white/[0.02] lg:flex-row lg:items-center"
                >

                  {/* IDENTIFICAÇÃO */}

                  <div className="min-w-0 flex-1">

                    <div className="mb-2 flex flex-wrap items-center gap-2">

                      <span className="rounded-md bg-emerald-500/10 px-2 py-1 font-mono-tech text-[10px] font-bold text-emerald-300">

                        {ticket.code ||
                          ticket.ticket_code ||
                          `#${String(ticket.id).slice(-6)}`}

                      </span>

                      <span
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${priorityClass(
                          ticket.priority
                        )}`}
                      >
                        {getPriorityLabel(
                          ticket.priority
                        )}
                      </span>

                      {ticket.archived && (
                        <span className="rounded-md border border-gray-500/20 bg-gray-500/5 px-2 py-1 text-[10px] text-gray-500">
                          Arquivado
                        </span>
                      )}

                    </div>

                    <div className="truncate text-sm font-semibold text-white">

                      {ticket.subject ||
                        ticket.title ||
                        ticket.description ||
                        "Chamado de suporte"}

                    </div>

                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-500">

                      <span>
                        Solicitante:{" "}
                        <span className="text-gray-400">
                          {ticket.requester_name ||
                            ticket.name ||
                            "Não informado"}
                        </span>
                      </span>

                      <span>
                        Sala:{" "}
                        <span className="text-gray-400">
                          {ticket.room ||
                            "Não informada"}
                        </span>
                      </span>

                      <span>
                        {getBuildingLabel(
                          ticket.building
                        )}
                      </span>

                      <span>
                        {formatDate(
                          ticket.created_at
                        )}
                      </span>

                    </div>

                  </div>

                  {/* STATUS */}

                  <div className="flex items-center gap-2">

                    <select
                      value={
                        ticket.status || "aberto"
                      }
                      onChange={(event) =>
                        changeStatus(
                          ticket.id,
                          event.target.value
                        )
                      }
                      className={`h-9 min-w-[155px] rounded-md border bg-black/20 px-3 text-xs font-medium outline-none transition-colors focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/30 ${statusClass(
                        ticket.status
                      )}`}
                      aria-label="Alterar status do chamado"
                    >

                      {STATUS_OPTIONS.map(
                        (option) => (

                          <option
                            key={option.value}
                            value={option.value}
                            className="bg-[#0a0f0d] text-white"
                          >
                            {option.label}
                          </option>

                        )
                      )}

                    </select>

                  </div>

                  {/* AÇÕES */}

                  <div className="flex items-center gap-2">

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setAuditTicket(ticket)
                      }
                      className="border-white/10 bg-transparent text-gray-400 hover:bg-white/[0.05] hover:text-white"
                    >

                      <History className="mr-2 h-4 w-4" />

                      Histórico

                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        toggleArchive(ticket)
                      }
                      className="border-white/10 bg-transparent text-gray-400 hover:bg-white/[0.05] hover:text-emerald-300"
                      title={
                        ticket.archived
                          ? "Restaurar chamado"
                          : "Arquivar chamado"
                      }
                    >

                      {ticket.archived ? (
                        <ArchiveRestore className="h-4 w-4" />
                      ) : (
                        <Archive className="h-4 w-4" />
                      )}

                    </Button>

                  </div>

                </div>

              ))}

            </div>

          )}

        </div>

      </main>

      {/* =====================================================
          HISTÓRICO
      ====================================================== */}

      <Dialog
        open={Boolean(auditTicket)}
        onOpenChange={(open) => {
          if (!open) {
            setAuditTicket(null);
          }
        }}
      >

        <DialogContent className="max-h-[85vh] overflow-y-auto border-white/10 bg-[#080c0a] text-white sm:max-w-2xl">

          <DialogHeader>

            <DialogTitle className="font-display text-lg">
              Histórico do chamado
            </DialogTitle>

          </DialogHeader>

          {auditTicket && (

            <div className="space-y-5">

              <div className="rounded-lg border border-white/5 bg-white/[0.02] p-4">

                <div className="mb-1 font-mono-tech text-[10px] uppercase tracking-wider text-emerald-500/60">
                  Chamado
                </div>

                <div className="font-semibold text-white">

                  {auditTicket.code ||
                    auditTicket.ticket_code ||
                    `#${String(
                      auditTicket.id
                    ).slice(-6)}`}

                </div>

                <div className="mt-2 text-sm text-gray-400">

                  {auditTicket.subject ||
                    auditTicket.title ||
                    auditTicket.description ||
                    "Chamado de suporte"}

                </div>

              </div>

              {Array.isArray(
                auditTicket.history
              ) &&
              auditTicket.history.length > 0 ? (

                <div className="space-y-3">

                  {auditTicket.history.map(
                    (item, index) => (

                      <div
                        key={
                          item.id ||
                          `${index}-${item.created_at || ""}`
                        }
                        className="relative rounded-lg border border-white/5 bg-white/[0.02] p-4"
                      >

                        <div className="flex items-start justify-between gap-3">

                          <div className="text-sm font-medium text-gray-200">

                            {item.action ||
                              item.event ||
                              item.description ||
                              "Alteração"}

                          </div>

                          <div className="shrink-0 text-[10px] text-gray-600">

                            {formatDate(
                              item.created_at ||
                                item.timestamp
                            )}

                          </div>

                        </div>

                        {(item.user ||
                          item.username ||
                          item.actor) && (

                          <div className="mt-1 text-[11px] text-gray-500">

                            Por:{" "}
                            {item.user ||
                              item.username ||
                              item.actor}

                          </div>

                        )}

                      </div>

                    )
                  )}

                </div>

              ) : (

                <div className="rounded-lg border border-white/5 bg-white/[0.02] p-6 text-center text-sm text-gray-600">

                  Nenhum histórico disponível.

                </div>

              )}

            </div>

          )}

        </DialogContent>

      </Dialog>

    </div>
  );
}