import React, { useState, useEffect, useRef } from 'react';
import { Zap, Loader2, CheckCircle2, AlertCircle, ChevronRight, Terminal, Database, Globe, Layout } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const API_URL = "http://localhost:8000";

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('ui'); // ui, api, db
  const [repairStatus, setRepairStatus] = useState(null); // SUCCESS, REPAIRED
  const [showSuccessPopup, setShowSuccessPopup] = useState(false);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleBuild = async () => {
    if (!prompt.trim()) return;
    
    setLoading(true);
    setLogs([{ step: "Initializing Pipeline...", status: "running" }]);
    setResult(null);
    setError(null);
    setRepairStatus(null);

    try {
      const response = await fetch(`/api/compile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim();
            if (!jsonStr) continue;
            
            try {
              const data = JSON.parse(jsonStr);
              
              if (data.step) {
                setLogs(prev => {
                  const existing = prev.findIndex(l => l.step === data.step);
                  if (existing !== -1) {
                    const newLogs = [...prev];
                    newLogs[existing] = { ...newLogs[existing], ...data };
                    return newLogs;
                  }
                  return [...prev, data];
                });

                if (data.data && (data.step.includes('Compiling') || data.partial)) {
                  setResult(data.data);
                }
                
                if (data.repair_status) {
                  setRepairStatus(data.repair_status);
                  setResult(data.data);
                }
              }
              
              if (data.final) {
                setShowSuccessPopup(true);
              }

              if (data.error) {
                setError(data.error);
                setLogs(prev => [...prev, { step: "Pipeline Failed", status: "error", error: data.error }]);
              }
            } catch (e) {
              console.error("Failed to parse chunk:", jsonStr);
            }
          }
        }
      }
    } catch (err) {
      setError("Failed to connect to backend. Is the server running?");
      setLogs(prev => [...prev, { step: "Connection Error", status: "error" }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-200">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500 rounded-lg shadow-lg shadow-indigo-500/20">
            <Zap className="w-5 h-5 text-white fill-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">AppCompiler <span className="text-indigo-400 font-normal">v1.0</span></h1>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-widest">SaaS Architecture Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-3 py-1 bg-slate-800 rounded-full border border-slate-700">
            <span className="text-[10px] font-bold text-slate-400">STATUS: READY</span>
          </div>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Left Column: Input & Logs */}
        <div className="w-1/2 flex flex-col gap-6">
          <section className="flex flex-col h-72 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 bg-slate-800/30">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <Terminal className="w-4 h-4 text-indigo-400" />
                Input App Blueprint
              </h2>
            </div>
            <div className="p-4 flex-1 flex flex-col gap-4">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Build a healthcare CRM with patient records, appointment scheduling, and doctor portals. Include billing and prescription management."
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none transition-all placeholder:text-slate-700"
              />
              <button
                onClick={handleBuild}
                disabled={loading || !prompt.trim()}
                className={cn(
                  "flex items-center justify-center gap-2 py-3 rounded-xl font-bold transition-all shadow-lg",
                  loading || !prompt.trim() 
                    ? "bg-slate-800 text-slate-500 cursor-not-allowed" 
                    : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20 active:scale-[0.98]"
                )}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />}
                {loading ? "Compiling..." : "Build SaaS Engine"}
              </button>
            </div>
          </section>

          <section className="flex-1 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col">
            <div className="p-4 border-b border-slate-800 bg-slate-800/30">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <Layout className="w-4 h-4 text-indigo-400" />
                Pipeline Execution Log
              </h2>
            </div>
            <div className="p-4 flex-1 overflow-y-auto space-y-3 font-mono text-[11px]">
              {logs.length === 0 && <p className="text-slate-600 italic">No activity yet...</p>}
              {logs.map((log, i) => (
                <div key={i} className="flex items-start gap-3 group">
                  <div className="mt-0.5">
                    {log.status === 'running' ? (
                      <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                    ) : log.status === 'completed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={cn(
                      "font-medium",
                      log.status === 'running' ? "text-indigo-300" : log.status === 'completed' ? "text-slate-300" : "text-rose-400"
                    )}>
                      {log.step}
                    </p>
                    {log.data && log.step.includes('Architecting') && (
                      <div className="mt-2 p-2 bg-slate-950 rounded border border-slate-800 text-[10px] text-slate-400 overflow-auto max-h-32">
                        <pre className="whitespace-pre-wrap">{log.data}</pre>
                      </div>
                    )}
                    {log.data && log.step.includes('Compiling') && (
                      <p className="text-emerald-500/70 mt-1 italic">âœ” Schemas cached for validation...</p>
                    )}
                  </div>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </section>
        </div>

        {/* Right Column: Schema Outputs */}
        <div className="w-1/2 flex flex-col bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
          <div className="flex border-b border-slate-800 bg-slate-800/30">
            <button
              onClick={() => setActiveTab('ui')}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-4 text-sm font-bold transition-all border-b-2",
                activeTab === 'ui' ? "border-indigo-500 text-indigo-400 bg-indigo-500/5" : "border-transparent text-slate-500 hover:text-slate-300"
              )}
            >
              <Layout className="w-4 h-4" /> UI Schema
            </button>
            <button
              onClick={() => setActiveTab('api')}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-4 text-sm font-bold transition-all border-b-2",
                activeTab === 'api' ? "border-emerald-500 text-emerald-400 bg-emerald-500/5" : "border-transparent text-slate-500 hover:text-slate-300"
              )}
            >
              <Globe className="w-4 h-4" /> API Endpoints
            </button>
              <button
                onClick={() => setActiveTab('db')}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-4 text-sm font-bold transition-all border-b-2",
                  activeTab === 'db' ? "border-amber-500 text-amber-400 bg-amber-500/5" : "border-transparent text-slate-500 hover:text-slate-300"
                )}
              >
                <Database className="w-4 h-4" /> DB Schema
              </button>
              {repairStatus && (
                <div className={cn(
                  "flex items-center gap-2 px-4 border-l border-slate-800",
                  repairStatus === 'REPAIRED' ? "text-amber-400" : "text-emerald-400"
                )}>
                  <div className={cn("w-2 h-2 rounded-full animate-pulse", repairStatus === 'REPAIRED' ? "bg-amber-400" : "bg-emerald-400")} />
                  <span className="text-[10px] font-bold uppercase tracking-tighter">
                    {repairStatus === 'REPAIRED' ? "Self-Repaired" : "Valid"}
                  </span>
                </div>
              )}
            </div>
          
          <div className="flex-1 overflow-hidden relative">
            {!result && !error && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-600 gap-4">
                <div className="p-6 bg-slate-950 rounded-full border border-slate-800">
                  <Terminal className="w-12 h-12 opacity-20" />
                </div>
                <p className="text-sm font-medium">Waiting for pipeline output...</p>
              </div>
            )}

            {error && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-rose-500 p-8 text-center gap-4">
                <AlertCircle className="w-12 h-12 opacity-50" />
                <p className="text-lg font-bold">Compilation Error</p>
                <p className="text-sm text-slate-400 max-w-md">{error}</p>
              </div>
            )}

            {result && (
              <div className="h-full overflow-auto p-6 bg-slate-950/50">
                <pre className="text-emerald-400 leading-relaxed">
                  {JSON.stringify(
                    activeTab === 'ui' ? result.ui_layout : activeTab === 'api' ? result.api_endpoints : result.db_schema, 
                    null, 2
                  )}
                </pre>
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="px-6 py-3 border-t border-slate-800 bg-slate-900/80 backdrop-blur-sm flex justify-between items-center">
        <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Proprietary AI Compiler Â© 2026</p>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            <span className="text-[10px] font-bold text-slate-400">LATENCY: {result ? "OPTIMIZED" : "---"}</span>
          </div>
        </div>
      </footer>
 
      {/* Success Popup Modal */}
      {showSuccessPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-3xl shadow-2xl max-w-md w-full flex flex-col items-center text-center gap-6 animate-in zoom-in-95 duration-300">
            <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center border border-emerald-500/20 shadow-lg shadow-emerald-500/10">
              <CheckCircle2 className="w-10 h-10 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white mb-2">Compilation Complete</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Your SaaS architecture engine has been successfully compiled and validated.
                {repairStatus === 'REPAIRED' 
                  ? " Minor consistency issues were detected and automatically repaired by the engine."
                  : " The system passed all cross-layer integrity checks on the first pass."}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 w-full">
              <div className="bg-slate-800/50 p-3 rounded-xl border border-slate-700/50">
                <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">UI Pages</p>
                <p className="text-sm font-bold text-white">{result?.ui_layout?.pages?.length || 0}</p>
              </div>
              <div className="bg-slate-800/50 p-3 rounded-xl border border-slate-700/50">
                <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Endpoints</p>
                <p className="text-sm font-bold text-white">{result?.api_endpoints?.endpoints?.length || 0}</p>
              </div>
              <div className="bg-slate-800/50 p-3 rounded-xl border border-slate-700/50">
                <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Status</p>
                <p className="text-sm font-bold text-emerald-400">Stable</p>
              </div>
            </div>
            <button
              onClick={() => setShowSuccessPopup(false)}
              className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-lg shadow-indigo-600/20 transition-all active:scale-[0.98]"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
