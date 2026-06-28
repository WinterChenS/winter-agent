interface ChatContainerProps {
  children: React.ReactNode;
}

export function ChatContainer({ children }: ChatContainerProps) {
  return (
    <div className="max-w-[820px] mx-auto w-full px-4 md:px-6 xl:px-8">
      {children}
    </div>
  );
}
