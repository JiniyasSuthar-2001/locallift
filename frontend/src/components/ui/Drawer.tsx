import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';
  closeOnBackdropClick?: boolean;
  closeOnEscape?: boolean;
  showCloseButton?: boolean;
  headerContent?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  zIndex?: number;
  'aria-label'?: string;
}

const maxWidthMap = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl'
};

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  children,
  footer,
  maxWidth = 'xl',
  closeOnBackdropClick = true,
  closeOnEscape = true,
  showCloseButton = true,
  headerContent,
  className = '',
  bodyClassName = '',
  zIndex = 9998,
  'aria-label': ariaLabel
}) => {
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

  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const maxWidthClass = maxWidthMap[maxWidth] || maxWidthMap.xl;

  const drawerElement = (
    <div
      className="fixed inset-0 overflow-hidden"
      style={{ zIndex }}
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : ariaLabel || 'Drawer'}
    >
      {/* ─── Viewport-level Backdrop ─── */}
      <div
        className="fixed inset-0 bg-slate-900/75 backdrop-blur-[2px] transition-opacity duration-300"
        onClick={closeOnBackdropClick ? onClose : undefined}
        aria-hidden="true"
      />

      {/* ─── Slide-Over Panel ─── */}
      <div className="fixed inset-y-0 right-0 pl-10 max-w-full flex">
        <div
          onClick={(e) => e.stopPropagation()}
          className={`w-screen ${maxWidthClass} bg-white border-l border-[#DCE8DC] flex flex-col shadow-2xl transform transition-transform duration-300 ease-in-out ${className}`}
        >
          {/* Header */}
          {(title || icon || headerContent || showCloseButton) && (
            <div className="px-5 sm:px-6 py-4 sm:py-5 border-b border-[#DCE8DC] bg-[#F7FAF7] flex items-center justify-between shrink-0">
              {headerContent ? (
                headerContent
              ) : (
                <div className="flex items-center space-x-3 min-w-0 pr-2">
                  {icon && (
                    <div className="w-9 h-9 rounded-xl bg-[#EAF2EA] border border-[#B8DFC9] flex items-center justify-center shrink-0 text-[#236B4F]">
                      {icon}
                    </div>
                  )}
                  <div className="min-w-0">
                    {title && (
                      <h3 className="text-base sm:text-lg font-black text-[#142820] tracking-tight truncate">
                        {title}
                      </h3>
                    )}
                    {subtitle && (
                      <p className="text-xs text-[#587568] font-medium mt-0.5 line-clamp-1">
                        {subtitle}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {showCloseButton && (
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close panel"
                  className="p-1.5 sm:p-2 rounded-xl text-[#587568] hover:text-[#142820] hover:bg-[#EAF2EA] transition-colors shrink-0 cursor-pointer"
                >
                  <X className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
              )}
            </div>
          )}

          {/* Scrollable Content */}
          <div className={`flex-1 overflow-y-auto ${bodyClassName}`}>
            {children}
          </div>

          {/* Optional Footer */}
          {footer && (
            <div className="px-5 sm:px-6 py-3.5 sm:py-4 border-t border-[#DCE8DC] bg-[#F7FAF7] flex items-center justify-end space-x-3 shrink-0">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(drawerElement, document.body);
};

export default Drawer;
