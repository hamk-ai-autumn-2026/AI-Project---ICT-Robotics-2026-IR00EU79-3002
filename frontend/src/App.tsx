import { useState } from "react";
import { StoryForm } from "./pages/StoryForm";
import { Story } from "./lib/stories";

// App-level view state. `createdStory` acts as a lightweight placeholder for
// routing until the full viewer (step 6) and dashboard (step 10) exist.
function App() {
  const [createdStory, setCreatedStory] = useState<Story | null>(null);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      {!createdStory && <StoryForm onCreated={setCreatedStory} />}

      {createdStory && (
        <div className="max-w-lg w-full bg-white rounded-2xl shadow p-8 space-y-4">
          <h1 className="text-2xl font-bold text-slate-800">
            Story saved! 🎉
          </h1>
          <p className="text-slate-500 text-sm">
            "{createdStory.childName}"'s storybook has been saved as a draft.
            Outline and page generation (Claude + illustrations) come in the
            next build steps.
          </p>
          <div className="text-sm bg-slate-100 rounded-lg p-4 space-y-1">
            <p><span className="font-semibold">Story ID:</span> {createdStory.id}</p>
            <p><span className="font-semibold">Status:</span> {createdStory.status}</p>
            <p><span className="font-semibold">Theme:</span> {createdStory.favoriteTheme}</p>
            <p><span className="font-semibold">Reading level:</span> {createdStory.readingLevel}</p>
            <p><span className="font-semibold">Moral:</span> {createdStory.moralLesson}</p>
          </div>
          <button
            onClick={() => setCreatedStory(null)}
            className="text-indigo-600 text-sm font-medium hover:underline"
          >
            ← Create another story
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
