import { useState } from "react";
import { useNavigate } from "react-router";
import { Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/app/context/auth-context";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const success = await login(email, password);
      if (success) {
        navigate("/dashboard");
      }
    } catch (err) {
      console.error("Login failed", err);
    }
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="w-[195px] mx-auto mb-6">
            <img src="/assets/glencore-logo.svg" className="w-full h-auto" alt="Glencore Logo" />
          </div>
          <p className="text-xs text-[#000000]">Kunnskapsbank & AI-Agent</p>
        </div>

        <div className="bg-white rounded-lg p-10 w-full border border-[#000000]/10">
          <div className="mb-6">
            <h2 className="text-xl text-[#000000] font-semibold mb-1">Logg inn</h2>
            <p className="text-base text-[#000000]">
              Skriv inn din e-postadresse og passord for å fortsette
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block text-sm text-[#000000] mb-2" htmlFor="email">
                E-postadresse
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 border border-[#000000]/20 rounded-md focus:ring-2 focus:ring-[#00AFAA] focus:border-transparent outline-none bg-[#ededed99] text-[#000000] placeholder:text-[#000000]/40 text-sm"
                placeholder="din.epost@glencore.com"
                autoComplete="email"
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm text-[#000000] mb-2" htmlFor="password">
                Passord
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                  className="w-full px-3 py-2.5 pr-10 border border-[#000000]/20 rounded-md focus:ring-2 focus:ring-[#00AFAA] focus:border-transparent outline-none bg-[#ededed99] text-[#000000] placeholder:text-[#000000]/40 text-sm [&::-ms-reveal]:hidden [&::-ms-clear]:hidden [&::-webkit-credentials-auto-fill-button]:hidden [&::-webkit-contacts-auto-fill-button]:hidden"
                  placeholder="········"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#000000] hover:text-[#000000]/60"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="flex items-center justify-between mb-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  id="remember"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 border-[#000000]/20 rounded text-[#00AFAA] focus:ring-[#00AFAA] accent-[#00AFAA]"
                />
                <span className="text-sm text-[#000000]">Husk meg</span>
              </label>
              <button
                type="button"
                className="text-sm text-[#00AFAA] hover:text-[#00AFAA]/80"
              >
                Glemt passord?
              </button>
            </div>

            <button
              type="submit"
              className="w-full bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white py-2.5 rounded-md transition-colors text-sm font-semibold"
            >
              Logg inn
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[#000000] mt-6 px-4 leading-relaxed">
          Ved å logge inn godtar du vilkårene for bruk av Glencore sine systemer.<br />
          Kun for autorisert personell.
        </p>
      </div>
    </div>
  );
}