export function formatConversationTitle(input: string) {
  const value = input.trim()
  if (!value) return "Nouvelle conversation"
  return value.length > 36 ? `${value.slice(0, 36)}...` : value
}

export function formatDateLabel(dateString: string) {
  const date = new Date(dateString)
  const now = new Date()

  const isSameDay =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()

  if (isSameDay) return "Aujourd’hui"

  const yesterday = new Date()
  yesterday.setDate(now.getDate() - 1)

  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear()

  if (isYesterday) return "Hier"

  return date.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
  })
}