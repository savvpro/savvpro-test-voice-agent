import { useState } from "react";
import "./App.css";

function App() {
  const [count, setCount] = useState<number>(0);

  return (
    <main className="app">
      <h1>React + TypeScript + Vite</h1>
      <p>Your frontend setup is working!</p>

      <button onClick={() => setCount((previous) => previous + 1)}>
        Count: {count}
      </button>
    </main>
  );
}

export default App;
