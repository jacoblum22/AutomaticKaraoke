import { API_BASE } from "./api/client";
import { ProgressTracker } from "./components/ProgressTracker";
import { UploadForm } from "./components/UploadForm";
import { VideoPlayer } from "./components/VideoPlayer";
import "./App.css";

function App() {
  return (
    <main className="app">
      <header>
        <h1>Automatic Karaoke</h1>
        <p className="subtitle">Phase 0 — scaffold ready</p>
      </header>

      <section className="stubs" aria-label="Phase 1 component stubs">
        <UploadForm />
        <ProgressTracker />
        <VideoPlayer />
      </section>

      <footer>
        <p>
          API base: <code>{API_BASE}</code>
        </p>
      </footer>
    </main>
  );
}

export default App;
