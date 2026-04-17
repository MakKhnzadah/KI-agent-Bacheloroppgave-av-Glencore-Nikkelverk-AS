import { Sidebar } from "@/app/components/sidebar";
import { FileText, Info, Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useDocuments } from "@/app/context/documents-context";
import { activityService } from "@/services";
import type { Activity } from "@/types";

export function DashboardPage() {
  const navigate = useNavigate();
  const { documents, getPendingDocuments } = useDocuments();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(true);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadActivities = async () => {
      setActivitiesLoading(true);
      setActivitiesError(null);

      try {
        const recentActivities = await activityService.getRecentActivities(5);
        if (!isMounted) return;
        setActivities(recentActivities);
      } catch (error) {
        if (!isMounted) return;
        console.error("Failed to load activities:", error);
        setActivitiesError("Kunne ikke hente aktivitet nå.");
      } finally {
        if (!isMounted) return;
        setActivitiesLoading(false);
      }
    };

    void loadActivities();

    return () => {
      isMounted = false;
    };
  }, []);
  
  const pendingCount = getPendingDocuments().length;
  const totalDocumentsCount = documents.length;
  
  const stats = [
    {
      label: "Hvordan fungerer det?",
      value: "",
      subtitle: "Lær om KI-systemet",
      icon: Info,
      iconColor: "text-[#475834]",
      iconBg: "bg-[#475834]/10",
      clickable: true,
      action: () => navigate("/upload"),
    },
    {
      label: "Venter Godkjenning",
      value: pendingCount.toString(),
      subtitle: "",
      icon: Clock,
      iconColor: "text-[#82131E]",
      iconBg: "bg-[#82131E]/10",
      clickable: true,
      action: () => navigate("/queue"),
    },
    {
      label: "Totalt Dokumenter",
      value: totalDocumentsCount.toLocaleString("nb-NO"),
      subtitle: "",
      icon: FileText,
      iconColor: "text-[#764484]",
      iconBg: "bg-[#764484]/10",
      clickable: true,
      action: () => navigate("/knowledge-bank"),
    },
  ];

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <h1 className="text-2xl text-[#000000] font-semibold">Oversikt</h1>
        </header>

        <div className="flex-1 overflow-auto px-6 pb-4">
          <div className="flex flex-col gap-4 pt-4">
            <div className="bg-white border border-white">
              <div className="grid grid-cols-3 gap-6 pt-6 px-6 mb-6">
                {stats.map((stat, index) => (
                  <div
                    key={index}
                    onClick={stat.clickable ? stat.action : undefined}
                    className={`bg-white rounded-[10px] p-6 border border-[#000000]/10 ${
                      stat.clickable ? "cursor-pointer hover:border-[#00AFAA] transition-colors" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className={`w-12 h-12 ${stat.iconBg} rounded-[10px] flex items-center justify-center`}>
                        <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
                      </div>
                    </div>
                    <h3 className="text-base text-[#000000] mb-1">{stat.label}</h3>
                    {stat.value && <p className="text-3xl text-[#000000] mb-1">{stat.value}</p>}
                    {stat.subtitle && <p className="text-sm text-[#000000]">{stat.subtitle}</p>}
                  </div>
                ))}
              </div>

              {/* Recent Activity */}
              <div className="bg-white rounded-[14px] p-6 mx-6 mb-6 border border-[#000000]/10">
                <div className="mb-6">
                  <h2 className="text-lg text-[#000000] font-semibold mb-1">Nylig aktivitet</h2>
                  <p className="text-base text-[#000000]/80">Siste oppdateringer i kunnskapsbanken</p>
                </div>
                {activitiesLoading && (
                  <p className="text-sm text-[#000000]/70">Laster aktivitet...</p>
                )}

                {!activitiesLoading && activitiesError && (
                  <p className="text-sm text-[#82131E]">{activitiesError}</p>
                )}

                {!activitiesLoading && !activitiesError && activities.length === 0 && (
                  <p className="text-sm text-[#000000]/70">Ingen nylig aktivitet enda.</p>
                )}

                {!activitiesLoading && !activitiesError && activities.length > 0 && (
                  <div className="space-y-6">
                    {activities.map((activity) => (
                      <div key={activity.id} className="flex items-start gap-4">
                        <div className="w-2 h-2 bg-[#00afaa] rounded-full mt-2.5 flex-shrink-0" />
                        <div className="flex-1">
                          <h3 className="text-base text-[#000000] mb-1">{activity.title}</h3>
                          <p className="text-base text-[#000000]/85 mb-1">{activity.description}</p>
                          <p className="text-xs text-[#000000]/70">
                            {activity.user} • {activity.time}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}