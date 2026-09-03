import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import PublicPage from "@/pages/PublicPage";
import LoginPage from "@/pages/LoginPage";
import AdminPage from "@/pages/AdminPage";
import { Loader2 } from "lucide-react";

const ProtectedRoute = ({ children }) => {
  const { user, ready } = useAuth();
  if (!ready)
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
      </div>
    );
  if (!user) return <Navigate to="/admin/login" replace />;
  return children;
};

const TOASTER_OPTIONS = {
  style: {
    background: "hsl(145 25% 9%)",
    border: "1px solid hsl(158 40% 25%)",
    color: "hsl(150 60% 96%)",
  },
};

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<PublicPage />} />
            <Route path="/admin/login" element={<LoginPage />} />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <AdminPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster
          position="top-right"
          theme="dark"
          toastOptions={TOASTER_OPTIONS}
        />
      </AuthProvider>
    </div>
  );
}

export default App;
