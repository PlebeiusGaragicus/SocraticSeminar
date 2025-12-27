<script lang="ts">
  import { WorkspaceLayout } from '$lib/components';
  import { Button } from '$lib/components/ui';

  // CypherTap integration - will be used for auth
  // import { Cyphertap, cyphertap } from 'cyphertap';

  // For now, simulate logged-in state for development
  let isLoggedIn = $state(false);
  let userNpub = $state<string | null>(null);

  function handleDemoLogin() {
    // Demo login - in production, use CypherTap
    isLoggedIn = true;
    userNpub = 'npub1demo...';
  }
</script>

{#if isLoggedIn}
  <!-- Main workspace -->
  <WorkspaceLayout {userNpub} />
{:else}
  <!-- Login screen -->
  <div class="flex h-screen w-full items-center justify-center bg-background">
    <div class="text-center">
      <h1 class="text-4xl font-bold tracking-tight text-foreground">Socratic Seminar</h1>
      <p class="mt-4 text-muted-foreground">Project-based agentic document editor</p>
      <p class="mt-2 text-sm text-muted-foreground/70">
        Powered by Nostr, Bitcoin eCash, and LangGraph
      </p>
      
      <div class="mt-8 flex flex-col items-center gap-4">
        <!-- CypherTap button would go here -->
        <!-- <Cyphertap /> -->
        
        <!-- Demo login for development -->
        <Button onclick={handleDemoLogin}>
          Demo Login (Development)
        </Button>
        
        <p class="text-xs text-muted-foreground">
          In production, use CypherTap for Nostr authentication
        </p>
      </div>
    </div>
  </div>
{/if}
