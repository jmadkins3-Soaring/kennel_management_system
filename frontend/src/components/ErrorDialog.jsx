import Modal from './Modal'

export default function ErrorDialog({ title, message, severity = 'red', onClose }) {
  const icon = severity === 'red' ? '🚫' : '⚠️'
  const style = severity === 'red'
    ? { background: '#ffebee', border: '1px solid #ef9a9a', borderRadius: 4, padding: '12px 16px' }
    : { background: '#fff8e1', border: '1px solid #ffe082', borderRadius: 4, padding: '12px 16px' }

  return (
    <Modal
      title={`${icon} ${title}`}
      size="sm"
      onClose={onClose}
      footer={<button className="btn btn-primary" onClick={onClose}>OK</button>}
    >
      <div style={style}>{message}</div>
    </Modal>
  )
}
