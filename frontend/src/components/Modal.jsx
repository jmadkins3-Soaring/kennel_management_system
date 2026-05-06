import { useEffect } from 'react'
import './Modal.css'

export default function Modal({ title, size = 'md', onClose, footer, children }) {
  useEffect(() => {
    const handler = e => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal modal-${size}`}>
        <div className="modal-header">
          <h2>{title}</h2>
          {onClose && <button className="modal-close" onClick={onClose}>✕</button>}
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
