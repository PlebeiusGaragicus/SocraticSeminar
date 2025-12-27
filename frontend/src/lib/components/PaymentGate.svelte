<script lang="ts">
  import { Zap } from '@lucide/svelte';
  import { Button } from './ui';
  import type { PaymentRequest } from '$lib/stores/types';

  interface Props {
    onPaymentReady: (payment: PaymentRequest | null) => void;
    disabled?: boolean;
  }

  let { onPaymentReady, disabled = false }: Props = $props();

  let paymentEnabled = $state(false);
  let paymentAmount = $state(10);

  // In production, this would use CypherTap to generate a real token
  // import { cyphertap } from 'cyphertap';

  async function generatePayment(): Promise<PaymentRequest | null> {
    if (!paymentEnabled) {
      return null;
    }

    // Development: generate a debug token
    // In production, use CypherTap:
    // const { token } = await cyphertap.generateEcashToken(paymentAmount, 'Agent query');
    
    const debugToken = `cashu_debug_${Date.now()}`;
    
    return {
      ecashToken: debugToken,
      amountSats: paymentAmount
    };
  }

  // Notify parent when payment settings change
  $effect(() => {
    if (paymentEnabled) {
      generatePayment().then(onPaymentReady);
    } else {
      onPaymentReady(null);
    }
  });
</script>

<div class="flex items-center gap-2 text-sm">
  <button
    onclick={() => paymentEnabled = !paymentEnabled}
    {disabled}
    class="flex items-center gap-1 rounded-md px-2 py-1 transition-colors
      {paymentEnabled 
        ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400' 
        : 'text-muted-foreground hover:bg-muted'}"
  >
    <Zap class="h-3 w-3" />
    <span>{paymentEnabled ? `${paymentAmount} sats` : 'Free mode'}</span>
  </button>

  {#if paymentEnabled}
    <select
      bind:value={paymentAmount}
      class="rounded-md border border-input bg-background px-2 py-1 text-xs"
    >
      <option value={5}>5 sats</option>
      <option value={10}>10 sats</option>
      <option value={25}>25 sats</option>
      <option value={50}>50 sats</option>
    </select>
  {/if}
</div>

