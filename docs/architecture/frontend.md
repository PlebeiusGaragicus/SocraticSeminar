# Frontend Architecture

## Technology Stack

- **Svelte 5** with runes for reactive state
- **SvelteKit** for routing and SSR capability
- **Tailwind CSS** for styling
- **shadcn-svelte** patterns for UI components
- **CypherTap** (submodule) for Nostr auth and eCash

## State Management

Uses Svelte 5 runes (`$state`, `$derived`, `$effect`) in `.svelte.ts` files:

```typescript
// Example: projects.svelte.ts
let projects = $state<Project[]>([]);
let currentProjectId = $state<string | null>(null);

const currentProject = $derived(
  projects.find(p => p.id === currentProjectId) ?? null
);

export const projectStore = {
  get projects() { return projects; },
  get currentProject() { return currentProject; },
  createProject,
  // ...
};
```

## Stores

| Store | Purpose |
|-------|---------|
| `projectStore` | Project CRUD and selection |
| `threadStore` | Thread and message management |
| `artifactStore` | Versioned artifact handling |
| `agentStore` | LangGraph streaming state |

## Components

### Layout
- `WorkspaceLayout` - Main three-panel layout
- `ProjectSidebar` - Project/thread/artifact navigation

### Chat
- `ThreadPanel` - Message display and input
- `PaymentGate` - eCash token toggle

### Artifacts
- `ArtifactPanel` - Document editor with versioning

## Agent Communication

```typescript
// From agent.svelte.ts
import { Client } from '@langchain/langgraph-sdk';

const client = new Client({ apiUrl: LANGGRAPH_URL });

// Stream response
const stream = client.runs.stream(threadId, ASSISTANT_ID, { input });

for await (const event of stream) {
  // Handle streaming events
}
```

## CypherTap Integration

CypherTap provides:
- Nostr authentication (NIP-07, NIP-49)
- eCash wallet management
- Token generation for payments

```svelte
<script>
  import { Cyphertap, cyphertap } from 'cyphertap';
  
  // Generate payment token
  const token = await cyphertap.generateEcashToken(amount, 'memo');
</script>

<Cyphertap />
```

