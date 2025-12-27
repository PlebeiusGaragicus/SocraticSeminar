<script lang="ts">
  import '../app.css';
  import { ModeWatcher, setMode } from 'mode-watcher';
  import { Toaster } from 'svelte-sonner';
  import { onMount } from 'svelte';

  let { children } = $props();

  // Force dark mode
  onMount(() => {
    setMode('dark');
  });
</script>

<ModeWatcher defaultMode="dark" />
<Toaster richColors position="top-right" theme="dark" />

{@render children()}
