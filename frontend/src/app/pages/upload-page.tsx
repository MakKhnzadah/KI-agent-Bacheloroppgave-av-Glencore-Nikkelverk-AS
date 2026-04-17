import { Sidebar } from "@/app/components/sidebar";
import { Upload, X, CheckCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useDocuments } from "@/app/context/documents-context";
import { useAuth } from "@/app/context/auth-context";
import { useToast } from "@/app/context/toast-context";

export function UploadPage() {
  const navigate = useNavigate();
  const { addDocument } = useDocuments();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [category, setCategory] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadComplete, setUploadComplete] = useState(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadComplete(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setUploadComplete(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setUploadProgress(0);
    setUploadComplete(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedFile || !category) return;

    setIsUploading(true);
    setUploadProgress(5);
    setUploadComplete(false);

    // Keep progress moving while request is in flight without forcing a fixed wait.
    const progressTimer = window.setInterval(() => {
      setUploadProgress((prev) => (prev >= 90 ? 90 : prev + 5));
    }, 160);

    try {
      await addDocument({
        file: selectedFile,
        category: category as any,
        uploadedBy: user?.name || "Ukjent bruker",
      });

      setUploadProgress(100);
      setUploadComplete(true);
      showToast("Dokument lastet opp. KI lager forslaget i bakgrunnen (kan ta litt tid) – sjekk Godkjenninger om litt.", "success");

      // Short pause so users can see completion state before redirect.
      window.setTimeout(() => {
        navigate("/queue");
      }, 900);
    } catch (error) {
      console.error("Failed to upload document:", error);
      setUploadComplete(false);
      setUploadProgress(0);
      const message = error instanceof Error ? error.message : "Ukjent feil";
      showToast(`Feil ved opplasting av dokument: ${message}`, "error");
    } finally {
      window.clearInterval(progressTimer);
      setIsUploading(false);
    }
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="h-[103px] bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <div className="flex items-center h-full px-6">
            <h1 className="text-2xl text-[#000000] font-semibold">Last opp dokument</h1>
          </div>
        </header>

        <div className="flex-1 overflow-auto pb-4">
          <div className="flex flex-col gap-4 pt-4 mx-6">
            <div className="bg-white border border-white px-6">
              <div className="py-6">
                <div className="border border-[#000000]/20 rounded-lg p-6 mb-6">
                  <h2 className="text-base font-semibold text-[#000000] mb-6">Hvordan fungerer det?</h2>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <div className="w-8 h-8 bg-[#00AFAA] text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-semibold">
                        1
                      </div>
                      <div className="flex-1 pt-0.5">
                        <h3 className="text-sm font-semibold text-[#000000] mb-1">Last opp dokumenter</h3>
                        <p className="text-sm text-[#000000]">Velg PDF, Word eller Excel-filer med prosessinformasjon</p>
                      </div>
                    </div>
                    <div className="flex gap-4">
                      <div className="w-8 h-8 bg-[#00AFAA] text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-semibold">
                        2
                      </div>
                      <div className="flex-1 pt-0.5">
                        <h3 className="text-sm font-semibold text-[#000000] mb-1">KI analyserer innholdet</h3>
                        <p className="text-sm text-[#000000]">Språkmodellen leser og forstår dokumentet, identifiserer nøkkelinformasjon</p>
                      </div>
                    </div>
                    <div className="flex gap-4">
                      <div className="w-8 h-8 bg-[#00AFAA] text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-semibold">
                        3
                      </div>
                      <div className="flex-1 pt-0.5">
                        <h3 className="text-sm font-semibold text-[#000000] mb-1">Godkjenn forslag</h3>
                        <p className="text-sm text-[#000000] mb-2">Gå til \"Godkjenninger\" for å se gjennom og godkjenne KI-forslag</p>
                        <div className="bg-[#F5F5F5] border border-[#000000]/10 rounded-md p-3 mt-2 space-y-2">
                          <div className="flex items-start gap-2">
                            <span className="text-[#00AFAA] font-semibold text-xs mt-0.5">✓</span>
                            <p className="text-xs text-[#000000]">
                              <span className="font-semibold">Godkjent KI-versjon:</span> Lagrer KI-forbedret dokument
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#82131E] font-semibold text-xs mt-0.5">✕</span>
                            <p className="text-xs text-[#000000]">
                              <span className="font-semibold">Ikke Godkjent:</span> Lukker vinduet og flytter dokumentet til avvist-listen
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-4">
                      <div className="w-8 h-8 bg-[#00AFAA] text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-semibold">
                        4
                      </div>
                      <div className="flex-1 pt-0.5">
                        <h3 className="text-sm font-semibold text-[#000000] mb-1">Kunnskapsbanken oppdateres</h3>
                        <p className="text-sm text-[#000000]">Godkjente endringer lagres automatisk i strukturert format</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border border-[#000000]/20 rounded-lg p-8">
                  <h2 className="text-lg font-semibold text-[#000000] mb-2">Last opp dokumenter</h2>
                  <p className="text-sm text-[#000000] mb-6">Last opp PDF, DOCX eller tekstfiler for KI-analyse</p>
                  
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    className="border-2 border-dashed border-[#000000]/20 rounded-lg p-12 mb-6 text-center bg-[#F5F5F5] hover:bg-[#EDEDED]/50 transition-colors"
                  >
                    <div className="flex justify-center mb-4">
                      <div className="w-12 h-12 bg-[#00AFAA]/10 rounded-lg flex items-center justify-center">
                        <Upload className="w-6 h-6 text-[#00AFAA]" />
                      </div>
                    </div>
                    <p className="text-sm font-semibold text-[#000000] mb-1">Dra og slipp filer her</p>
                    <p className="text-xs text-[#000000] mb-4">eller klikk for å velge filer</p>
                    <label>
                      <input
                        type="file"
                        className="hidden"
                        accept=".pdf,.docx,.txt"
                        onChange={handleFileSelect}
                      />
                      <span className="inline-block px-6 py-2 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors cursor-pointer text-sm font-semibold">
                        Velg filer
                      </span>
                    </label>
                    {selectedFile && (
                       <p className="text-xs font-semibold text-[#000000] mt-4">Valgt fil: {selectedFile.name}</p>
                     )}
                   </div>
                   
                   {selectedFile && !uploadComplete && (
                     <div className="border border-[#000000]/20 rounded-lg p-4 mb-6 bg-[#F5F5F5]">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-[#00AFAA]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                            <Upload className="w-5 h-5 text-[#00AFAA]" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#000000]">{selectedFile.name}</p>
                            <p className="text-xs font-semibold text-[#000000]">
                              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleRemoveFile}
                          className="p-2 hover:bg-[#000000]/5 rounded-md transition-colors"
                        >
                          <X className="w-5 h-5 text-[#000000]" />
                        </button>
                      </div>

                      {/* Upload Progress */}
                      {isUploading && (
                        <div className="mt-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-[#000000]">Laster opp...</span>
                            <span className="text-xs text-[#000000] font-semibold">{uploadProgress}%</span>
                          </div>
                          <div className="w-full h-2 bg-[#000000]/10 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-[#00AFAA] transition-all duration-300"
                              style={{ width: `${uploadProgress}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {uploadComplete && (
                    <div className="border border-[#475834]/20 rounded-lg p-6 mb-6 bg-[#475834]/5">
                      <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 bg-[#475834]/10 rounded-full flex items-center justify-center">
                          <CheckCircle className="w-6 h-6 text-[#475834]" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-[#000000]">Opplasting fullført!</p>
                          <p className="text-xs text-[#000000]">Dokumentet analyseres nå av KI...</p>
                        </div>
                      </div>
                      <p className="text-xs text-[#000000]">Du vil bli omdirigert til godkjenningssiden.</p>
                    </div>
                  )}
                  
                  <p className="text-xs text-[#000000] text-center mb-6">
                    Støttede formater: PDF, DOCX, TXT (maks 10MB)
                  </p>

                  <div className="grid grid-cols-1 gap-4 mb-6">
                    <div>
                      <label className="block text-sm font-semibold text-[#000000] mb-2">Kategori</label>
                      <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="w-full px-4 py-2.5 border border-[#000000]/20 rounded-md text-sm text-[#000000] focus:outline-none focus:ring-2 focus:ring-[#00AFAA] focus:border-transparent appearance-none bg-white"
                      >
                        <option value="">Velg kategori...</option>
                        <option value="prosedyre">Prosedyre</option>
                        <option value="sikkerhet">Sikkerhet</option>
                        <option value="vedlikehold">Vedlikehold</option>
                        <option value="kvalitet">Kvalitet</option>
                      </select>
                    </div>
                  </div>

                  {selectedFile && (
                    <p className="text-xs text-[#000000]/70 mb-6">
                      Tittel settes automatisk fra filnavn nå, og kan endres senere før godkjenning.
                    </p>
                  )}

                  <form onSubmit={handleSubmit}>
                    <button 
                      type="submit"
                      disabled={!selectedFile || isUploading || uploadComplete}
                      className="w-full py-3 bg-[#00AFAA] hover:bg-[#00AFAA]/90 disabled:bg-[#000000]/20 disabled:cursor-not-allowed text-white rounded-md transition-colors text-sm font-semibold"
                    >
                      {isUploading ? "Laster opp..." : uploadComplete ? "Fullført!" : "Last opp og analyser"}
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}