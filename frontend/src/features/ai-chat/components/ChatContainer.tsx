interface ChatContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function ChatContainer({ children, className = "" }: ChatContainerProps) {
  return (
    <div className={`max-w-[820px] mx-auto w-full px-4 md:px-6 xl:px-8 ${className}`}>
      {children}
    </div>
  );
}
