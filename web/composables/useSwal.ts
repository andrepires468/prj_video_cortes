export function useSwal() {
  const { $swal } = useNuxtApp()
  return $swal
}

export function swalTheme(): 'dark' | 'light' {
  if (import.meta.client && document.documentElement.getAttribute('data-theme') === 'dark') {
    return 'dark'
  }
  return 'light'
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export type ConfirmDeleteKind = 'video' | 'corte'

export async function confirmDangerousDelete(options: {
  filename: string
  kind: ConfirmDeleteKind
  cortesCount?: number
  cortesUnknown?: boolean
}): Promise<boolean> {
  const swal = useSwal()
  const theme = swalTheme()
  const name = escapeHtml(options.filename)
  const cortesCount = options.cortesCount ?? 0

  const isVideo = options.kind === 'video'
  let html = isVideo
    ? `O arquivo <strong>${name}</strong> será excluído permanentemente.`
    : `O corte <strong>${name}</strong> será excluído permanentemente.`

  if (isVideo && options.cortesUnknown) {
    html += '<br><br>Não foi possível verificar os cortes. Se existirem, eles também serão deletados.'
  } else if (isVideo && cortesCount > 0) {
    const label = cortesCount === 1 ? '1 corte' : `${cortesCount} cortes`
    html += `<br><br>Este vídeo tem <strong>${label}</strong>. ${
      cortesCount === 1 ? 'Ele também será deletado.' : 'Eles também serão deletados.'
    }`
  }

  const first = await swal.fire({
    title: isVideo ? 'Remover vídeo?' : 'Remover corte?',
    html,
    icon: 'warning',
    theme,
    showCancelButton: true,
    showDenyButton: false,
    focusCancel: true,
    reverseButtons: true,
    confirmButtonText: 'Continuar',
    cancelButtonText: 'Cancelar',
    confirmButtonColor: '#d33',
  })

  if (!first.isConfirmed) return false

  const second = await swal.fire({
    title: 'Confirmação final',
    html: 'Esta ação não pode ser desfeita.<br>Digite <strong>DELETE</strong> para confirmar.',
    input: 'text',
    inputPlaceholder: 'DELETE',
    inputAttributes: {
      autocomplete: 'off',
      autocapitalize: 'off',
      spellcheck: 'false',
    },
    icon: 'warning',
    theme,
    showCancelButton: true,
    showDenyButton: false,
    focusCancel: true,
    reverseButtons: true,
    confirmButtonText: 'Excluir',
    cancelButtonText: 'Cancelar',
    confirmButtonColor: '#d33',
    inputValidator: (value) => {
      if (value !== 'DELETE') {
        return 'Digite DELETE (em maiúsculas) para confirmar.'
      }
      return null
    },
  })

  return second.isConfirmed
}
