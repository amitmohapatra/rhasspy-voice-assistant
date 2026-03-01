'use client';

/**
 * RAG Pipeline Detail Page - Redirect
 *
 * Individual pipeline editing no longer exists (pipeline is fully automated).
 * Redirect to the main pipeline info page.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RAGPipelineDetailPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/platform/rag-pipelines');
  }, [router]);

  return null;
}
