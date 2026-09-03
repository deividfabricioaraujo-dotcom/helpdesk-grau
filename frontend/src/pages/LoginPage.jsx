import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ArrowLeft, LogIn } from "lucide-react";
import { Link } from "react-router-dom";

export default function LoginPage() {
  const { login, user, ready } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (ready && user) navigate("/admin", { replace: true });
  }, [ready, user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const res = await login(username.trim(), password);
    setLoading(false);
    if (res.ok) {
      toast.success("Bem-vindo de volta!");
      navigate("/admin", { replace: true });
    } else {
      setError(res.error);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background grid-backdrop px-4">
      <div className="w-full max-w-sm animate-fade-up">
        <Link
          to="/"
          className="mb-6 inline-flex items-center gap-1.5 text-xs text-emerald-400/70 transition-colors hover:text-emerald-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar ao início
        </Link>

        <div className="rounded-2xl border border-emerald-500/15 bg-[#141F18]/70 p-7 shadow-2xl shadow-black/50">
          <div className="mb-6 flex justify-center">
            <Logo variant="ti" />
          </div>
          <h1 className="text-center font-display text-xl font-bold text-emerald-50">Acesso Técnico</h1>
          <p className="mt-1 text-center text-xs text-gray-400">Painel de gestão de chamados</p>

          <form onSubmit={submit} data-testid="admin-login-form" className="mt-6 space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-wider text-emerald-400/80">Usuário</Label>
              <Input
                data-testid="admin-input-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="seu usuário"
                autoComplete="username"
                className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-emerald-400/80">Senha</Label>
              <Input
                data-testid="admin-input-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                className="mt-1.5 border-emerald-500/20 bg-black/30 text-emerald-50 placeholder:text-emerald-500/30 focus-visible:ring-emerald-500"
              />
            </div>
            {error && (
              <p data-testid="login-error" className="text-sm text-red-400">
                {error}
              </p>
            )}
            <Button
              type="submit"
              data-testid="admin-btn-login"
              disabled={loading}
              className="w-full bg-emerald-500 font-semibold text-black hover:bg-emerald-400"
            >
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogIn className="mr-2 h-4 w-4" />}
              Entrar
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
