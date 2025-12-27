<script lang="ts">
  import { ChevronLeft, ChevronRight, Save } from '@lucide/svelte';
  import { Button, Textarea } from './ui';
  import { artifactStore } from '$lib/stores';

  let editedContent = $state('');
  let editedTitle = $state('');
  let isEditing = $state(false);

  const currentArtifact = $derived(artifactStore.currentArtifact);
  const currentContent = $derived(() => {
    if (!currentArtifact) return null;
    return currentArtifact.versions[currentArtifact.currentVersionIndex] ?? null;
  });

  // Sync edited content when artifact changes
  $effect(() => {
    const content = currentContent();
    if (content && !isEditing) {
      editedContent = content.content;
      editedTitle = content.title;
    }
  });

  function handleSave() {
    if (!currentArtifact || !editedContent.trim()) return;
    
    artifactStore.updateArtifact(
      currentArtifact.id,
      editedTitle || 'Untitled',
      editedContent,
      currentContent()?.language
    );
    isEditing = false;
  }

  function handlePrevVersion() {
    if (!currentArtifact) return;
    const newIndex = currentArtifact.currentVersionIndex - 1;
    if (newIndex >= 0) {
      artifactStore.setArtifactVersion(currentArtifact.id, newIndex);
    }
  }

  function handleNextVersion() {
    if (!currentArtifact) return;
    const newIndex = currentArtifact.currentVersionIndex + 1;
    if (newIndex < currentArtifact.versions.length) {
      artifactStore.setArtifactVersion(currentArtifact.id, newIndex);
    }
  }

  const canGoPrev = $derived(
    currentArtifact && currentArtifact.currentVersionIndex > 0
  );
  const canGoNext = $derived(
    currentArtifact && currentArtifact.currentVersionIndex < currentArtifact.versions.length - 1
  );
</script>

<div class="flex h-full flex-col">
  {#if !currentArtifact}
    <!-- Empty state -->
    <div class="flex h-full items-center justify-center text-muted-foreground">
      <p>Select an artifact to view or edit</p>
    </div>
  {:else}
    <!-- Header with version navigation -->
    <div class="flex items-center justify-between border-b border-border p-4">
      <div class="flex items-center gap-2">
        <input
          type="text"
          bind:value={editedTitle}
          onfocus={() => isEditing = true}
          class="border-none bg-transparent text-lg font-semibold focus:outline-none"
          placeholder="Untitled"
        />
        <span class="text-sm text-muted-foreground">
          ({currentArtifact.type})
        </span>
      </div>
      
      <div class="flex items-center gap-2">
        <!-- Version navigation -->
        <div class="flex items-center gap-1 text-sm text-muted-foreground">
          <Button 
            variant="ghost" 
            size="icon" 
            onclick={handlePrevVersion}
            disabled={!canGoPrev}
          >
            <ChevronLeft class="h-4 w-4" />
          </Button>
          <span>
            v{currentArtifact.currentVersionIndex + 1}/{currentArtifact.versions.length}
          </span>
          <Button 
            variant="ghost" 
            size="icon" 
            onclick={handleNextVersion}
            disabled={!canGoNext}
          >
            <ChevronRight class="h-4 w-4" />
          </Button>
        </div>

        <!-- Save button -->
        {#if isEditing}
          <Button size="sm" onclick={handleSave}>
            <Save class="mr-2 h-4 w-4" />
            Save
          </Button>
        {/if}
      </div>
    </div>

    <!-- Content editor -->
    <div class="flex-1 overflow-hidden p-4">
      {#if currentArtifact.type === 'code'}
        <!-- Code editor -->
        <textarea
          bind:value={editedContent}
          onfocus={() => isEditing = true}
          class="h-full w-full resize-none rounded-md border border-input bg-muted/50 p-4 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          spellcheck="false"
        ></textarea>
      {:else}
        <!-- Markdown/text editor -->
        <textarea
          bind:value={editedContent}
          onfocus={() => isEditing = true}
          class="h-full w-full resize-none rounded-md border border-input bg-background p-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        ></textarea>
      {/if}
    </div>

    <!-- Footer with metadata -->
    <div class="border-t border-border p-2 text-xs text-muted-foreground">
      {#if currentContent()}
        Last updated: {new Date(currentContent()!.createdAt).toLocaleString()}
      {/if}
    </div>
  {/if}
</div>

