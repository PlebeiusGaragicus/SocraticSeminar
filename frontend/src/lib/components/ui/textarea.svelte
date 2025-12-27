<script lang="ts">
  import { cn } from '$lib/utils';

  interface Props {
    class?: string;
    placeholder?: string;
    value?: string;
    disabled?: boolean;
    rows?: number;
    oninput?: (e: Event) => void;
    onkeydown?: (e: KeyboardEvent) => void;
  }

  let {
    class: className = '',
    placeholder = '',
    value = $bindable(''),
    disabled = false,
    rows = 3,
    oninput,
    onkeydown
  }: Props = $props();
</script>

<textarea
  {placeholder}
  {disabled}
  {rows}
  bind:value
  {oninput}
  {onkeydown}
  class={cn(
    'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
    className
  )}
></textarea>

