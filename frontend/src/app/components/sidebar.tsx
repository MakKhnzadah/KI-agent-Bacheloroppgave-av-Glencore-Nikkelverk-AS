import { useNavigate, useLocation } from "react-router";
import { LayoutGrid, Upload, CheckCircle, FileText, Database, LogOut } from "lucide-react";
import { useAuth } from "@/app/context/auth-context";
import { useDocuments } from "@/app/context/documents-context";
import { canAccessExpertFeatures, defaultPathForRole, normalizeUserRole } from "@/utils/role-access";

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { getPendingDocuments } = useDocuments();

  const pendingCount = getPendingDocuments().length;
  const role = normalizeUserRole(user?.role);
  const expertAccess = canAccessExpertFeatures(role);

  const menuItems = expertAccess
    ? [
        { path: "/dashboard", label: "Oversikt", icon: LayoutGrid },
        { path: "/upload", label: "Last opp dokument", icon: Upload },
        { path: "/queue", label: "Til godkjenning", icon: CheckCircle, badge: pendingCount },
        { path: "/knowledge-bank", label: "Kunnskapsbank", icon: FileText },
        { path: "/files", label: "Filer", icon: Database },
      ]
    : [{ path: "/knowledge-bank", label: "Kunnskapsbank", icon: FileText }];

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="w-[278px] bg-white flex flex-col h-screen border-r border-[#00AFAA]/30">
      {/* Logo Section */}
      <div className="h-[124px] flex items-center justify-center border-b border-[#000000]/10 text-center">
        <button
          onClick={() => navigate(defaultPathForRole(role))}
          className="flex flex-col items-center gap-4 hover:opacity-80 transition-opacity cursor-pointer"
        >
          <img src="/assets/glencore-logo.svg" className="w-[210px] h-auto object-contain" alt="Glencore Logo" />
          <p className="text-sm text-[#000000]/70 text-center">Kunnskapsbank & KI-agent</p>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 pt-3">
        <div className="space-y-[13px]">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-[10px] transition-colors relative group ${isActive
                  ? "bg-[#00AFAA]/10 text-[#00AFAA]"
                  : "text-[#000000] hover:text-[#00AFAA]"
                  }`}
              >
                {/* Active Indicator Line */}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-[#00AFAA] rounded-r-full" />
                )}
                <Icon className="w-5 h-5" />
                <span className="text-base font-normal">{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="min-w-[20px] h-5 px-2 bg-[#82131E] text-white text-xs rounded-lg flex items-center justify-center font-semibold">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-[#000000]/10">
        <div className="flex items-center gap-3 px-2 py-3 mb-2">
          <div className="w-12 h-12 bg-[#00AFAA] rounded-full flex items-center justify-center flex-shrink-0">
            <span className="text-white text-sm font-bold">{user?.initials || "EB"}</span>
          </div>
          <div className="flex-1">
            <p className="text-base text-[#000000] font-medium leading-tight">{user?.name || "Ekspert Bruker"}</p>
            <p className="text-sm text-[#000000]/60 font-normal leading-tight">{role || "employee"}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-2 py-3 text-[#000000] hover:text-[#00AFAA] transition-colors rounded-[10px]"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-base">Logg ut</span>
        </button>
      </div>
    </div>
  );
}