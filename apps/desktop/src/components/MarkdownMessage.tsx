import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownMessageProps {
  content: string;
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // 代码块
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          const isInline = !className;

          if (isInline) {
            return (
              <code className="markdown-inline-code" {...props}>
                {children}
              </code>
            );
          }

          return (
            <div className="markdown-code-block">
              {match && <span className="markdown-code-lang">{match[1]}</span>}
              <pre className="markdown-pre">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            </div>
          );
        },
        // 段落
        p({ children }) {
          return <p className="markdown-paragraph">{children}</p>;
        },
        // 列表
        ul({ children }) {
          return <ul className="markdown-list">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="markdown-list markdown-ordered-list">{children}</ol>;
        },
        li({ children }) {
          return <li className="markdown-list-item">{children}</li>;
        },
        // 链接
        a({ children, href }) {
          return (
            <a href={href} className="markdown-link" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          );
        },
        // 标题
        h1({ children }) {
          return <h1 className="markdown-heading markdown-h1">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="markdown-heading markdown-h2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="markdown-heading markdown-h3">{children}</h3>;
        },
        // 引用
        blockquote({ children }) {
          return <blockquote className="markdown-blockquote">{children}</blockquote>;
        },
        // 表格
        table({ children }) {
          return <div className="markdown-table-wrapper"><table className="markdown-table">{children}</table></div>;
        },
        th({ children }) {
          return <th className="markdown-th">{children}</th>;
        },
        td({ children }) {
          return <td className="markdown-td">{children}</td>;
        },
        // 分割线
        hr() {
          return <hr className="markdown-hr" />;
        },
        // 强调
        strong({ children }) {
          return <strong className="markdown-strong">{children}</strong>;
        },
        em({ children }) {
          return <em className="markdown-em">{children}</em>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
