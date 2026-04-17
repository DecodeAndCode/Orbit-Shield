import Header from "./components/Header";
import ConjunctionTimeline from "./components/ConjunctionTimeline";
import GlobeView from "./components/GlobeView";
import EventDetailPanel from "./components/EventDetailPanel";
import AlertConfigForm from "./components/AlertConfigForm";

export default function App() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 border-r border-[var(--color-border)] overflow-y-auto bg-[var(--color-bg-secondary)]">
          <ConjunctionTimeline />
        </aside>
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 bg-[var(--color-bg-primary)]">
            <GlobeView />
          </div>
          <div className="h-64 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto">
            <EventDetailPanel />
          </div>
        </main>
      </div>
      <AlertConfigForm />
    </div>
  );
}
