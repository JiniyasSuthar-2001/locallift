import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode | React.ElementType;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?:
    | 'sm'
    | 'md'
    | 'lg'
    | 'xl'
    | '2xl'
    | '3xl'
    | '4xl'
    | '5xl'
    | 'full'
    | 'max-w-sm'
    | 'max-w-md'
    | 'max-w-lg'
    | 'max-w-xl'
    | 'max-w-2xl'
    | 'max-w-3xl'
    | 'max-w-4xl'
    | 'max-w-5xl'
    | 'max-w-full'
    | string;
  closeOnBackdropClick?: boolean;
  closeOnOutsideClick?: boolean;
  closeOnEscape?: boolean;
  showCloseButton?: boolean;
  headerContent?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  zIndex?: number;
  'aria-label'?: string;
}

const maxWidthMap: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
  '4xl': 'max-w-4xl',
  '5xl': 'max-w-5xl',
  full: 'max-w-[calc(100vw-2rem)]',
  'max-w-sm': 'max-w-sm',
  'max-w-md': 'max-w-md',
  'max-w-lg': 'max-w-lg',
  'max-w-xl': 'max-w-xl',
  'max-w-2xl': 'max-w-2xl',
  '3xl-w': 'max-w-3xl',
  'max-w-3xl': 'max-w-3xl',
  'max-w-4xl': 'max-w-4xl',
  'max-w-5xl': 'max-w-5xl',
  'max-w-full': 'max-w-[calc(100vw-2rem)]'
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  description,
  icon,
  children,
  footer,
  maxWidth = 'lg',
  closeOnBackdropClick,
  closeOnOutsideClick,
  closeOnEscape = true,
  showCloseButton = true,
  headerContent,
  className = '',
  bodyClassName = '',
  zIndex = 9999,
  'aria-label': ariaLabel
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const shouldCloseOnBackdrop = closeOnOutsideClick ?? closeOnBackdropClick ?? true;
  const effectiveSubtitle = subtitle || description;

  // Close on Escape key
  useEffect(() => {
    if (!isOpen || !closeOnEscape) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, closeOnEscape, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const maxWidthClass = maxWidthMap[maxWidth] || maxWidthMap.lg;

  const modalElement = (
    <div
      className="fixed inset-0 flex items-center justify-center p-3 sm:p-4 md:p-6 select-none-backdrop"
      style={{ zIndex }}
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : ariaLabel || 'Dialog'}
    >
      {/* ─── Global Viewport Backdrop ─── */}
      <div
        className="fixed inset-0 bg-slate-900/75 backdrop-blur-[2px] transition-opacity duration-200"
        onClick={shouldCloseOnBackdrop ? onClose : undefined}
        aria-hidden="true"
      />

      {/* ─── Modal Surface / Card ─── */}
      <div
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
        className={`relative z-10 w-full ${maxWidthClass} max-h-[92vh] flex flex-col bg-white rounded-2xl sm:rounded-3xl shadow-2xl border border-[#DCE8DC] overflow-hidden transform transition-all duration-200 animate-in fade-in zoom-in-95 ${className}`}
      >
        {/* Header if title/icon/headerContent provided */}
        {(title || icon || headerContent || showCloseButton) && (
          <div className="px-5 sm:px-6 py-4 sm:py-5 border-b border-[#DCE8DC] bg-[#F7FAF7] flex items-center justify-between shrink-0">
            {headerContent ? (
              headerContent
            ) : (
              <div className="flex items-center space-x-3 min-w-0 pr-2">
                {icon && (
                  <div className="w-10 h-10 rounded-xl bg-[#EAF2EA] border border-[#B8DFC9] flex items-center justify-center shrink-0 text-[#236B4F]">
                    {React.isValidElement(icon) ? (
                      icon
                    ) : typeof icon === 'function' || typeof icon === 'object' ? (
                      React.createElement(icon as React.ElementType, { className: 'w-5 h-5' })
                    ) : (
                      icon
                    )}
                  </div>
                )}
                <div className="min-w-0">
                  {title && (
                    <h3 className="text-base sm:text-lg font-black text-[#142820] tracking-tight truncate">
                      {title}
                    </h3>
                  )}
                  {effectiveSubtitle && (
                    <p className="text-xs text-[#587568] font-medium mt-0.5 line-clamp-1">
                      {effectiveSubtitle}
                    </p>
                  )}
                </div>
              </div>
            )}

            {showCloseButton && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                className="p-1.5 sm:p-2 rounded-xl text-[#587568] hover:text-[#142820] hover:bg-[#EAF2EA] transition-colors shrink-0 cursor-pointer"
              >
                <X className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
            )}
          </div>
        )}

        {/* Scrollable Body Content */}
        <div className={`p-5 sm:p-6 overflow-y-auto flex-1 text-[#2E4E40] ${bodyClassName}`}>
          {children}
        </div>

        {/* Optional Sticky Footer */}
        {footer && (
          <div className="px-5 sm:px-6 py-3.5 sm:py-4 border-t border-[#DCE8DC] bg-[#F7FAF7] flex items-center justify-end space-x-3 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalElement, document.body);
};

export default Modal;
