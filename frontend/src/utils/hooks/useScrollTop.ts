import { useEffect, useState } from 'react';

export const useScrollTop = (): [() => void] => {
  const [scrollTop, setScrollTop] = useState(false);

  const scrollToTop = (): void => {
    setScrollTop(true);
  };

  useEffect(() => {
    if (scrollTop) {
      const el = document.getElementById('pc-task-item-container');
      el?.scroll({
        top: 0,
        behavior: 'smooth',
      });
      setScrollTop(() => false);
    }
  }, [scrollTop]);

  return [scrollToTop];
};
