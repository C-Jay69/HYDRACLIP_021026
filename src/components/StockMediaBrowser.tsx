import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Input as InputComponent } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Grid, Image as NextImage } from "lucide-react";

export interface ShutterstockImage {
  id: number;
  title: string;
  description: string;
  url: string;
  preview_url: string;
  thumbnail_url: string;
  license_type: string;
  price: number;
  contributor: string;
  width: number;
  height: number;
}

export interface ShutterstockVideo {
  id: number;
  title: string;
  description: string;
  preview_url: string;
  thumbnail_url: string;
  license_type: string;
  price: number;
  duration: string;
  width: number;
  height: number;
}

export function useShutterstockSearch() {
  const [images, setImages] = useState<ShutterstockImage[]>([]);
  const [videos, setVideos] = useState<ShutterstockVideo[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [currentPage, setCurrentPage] = useState<number>(1);

  const search = async (
    query: string,
    mediaType: "image" | "video" = "image",
    page: number = 1,
    perPage: number = 25,
  ) => {
    setLoading(true);
    setError(null);
    setHasMore(true);
    setImages([]);
    setVideos([]);

    try {
      const response = await fetch(
        `/api/shutterstock/${mediaType}/search?query=${encodeURIComponent(
          query,
        )}&page=${page}&per_page=${perPage}`,
        {
          credentials: "include",
        },
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Shutterstock search failed");
      }

      const data = await response.json();

      if (mediaType === "image") {
        setImages(data.data?.images || []);
      } else {
        setVideos(data.data?.videos || []);
      }

      setHasMore(data.meta?.has_more || false);
      setCurrentPage(page);
    } catch (err: any) {
      setError(err.message || "An error occurred during search");
      console.error("Shutterstock search error:", err);
    } finally {
      setLoading(false);
    }
  };

  return {
    images,
    videos,
    loading,
    error,
    hasMore,
    currentPage,
    search,
  };
}

export function StockMediaBrowser() {
  const { images, videos, loading, error, hasMore, currentPage, search } =
    useShutterstockSearch();

  const [query, setQuery] = useState("");
  const [mediaType, setMediaType] = useState<"image" | "video">("image");

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await search(query, mediaType, 1);
  };

  const loadMore = async () => {
    if (!hasMore || loading) return;
    await search(query, mediaType, currentPage + 1);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <span>Loading...</span>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4">
      {/* Search Form */}
      <form onSubmit={handleSearch} className="mb-6 flex flex-col sm:flex-row gap-3">
        <Input
          type="text"
          placeholder="Search stock media..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <Select
          onChange={(e) => setMediaType(e.target.value as "image" | "video")}
          disabled={loading}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Media Type" />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="image">Images</SelectItem>
            <SelectItem value="video">Videos</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" disabled={loading} variant="primary">
          {loading ? "Searching..." : "Search"}
        </Button>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-100 rounded border-red-400 text-red-700">
          {error}
        </div>
      )}

      {/* Image Results */}
      {mediaType === "image" && images.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {images.map((image) => (
            <Card key={image.id} className="hover:shadow-lg transition-shadow">
              <img
                src={image.preview_url}
                alt={image.title}
                className="w-full h-48 object-cover rounded-t"
              />
              <div className="p-3">
                <h4 className="font-medium text-sm line-clamp-2">{image.title}</h4>
                <p className="text-caption text-xs text-muted-foreground line-clamp-1">
                  {image.description}
                </p>
                <div className="mt-2 flex justify-between text-xs">
                  <span>{image.contributor}</span>
                  <span>{image.license_type.toUpperCase()} • ${image.price}</span>
                </div>
              </div>
            </Card>
          ))}
          {hasMore && !loading && (
            <div key="load-more" className="col-span-full flex justify-center py-4">
              <button onClick={loadMore} className="text-sm text-primary hover:underline">
                Load more
              </button>
            </div>
          )}
        </div>
      )}

      {/* Video Results */}
      {mediaType === "video" && videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video) => (
            <Card key={video.id} className="hover:shadow-lg transition-shadow">
              <NextImage
                src={video.thumbnail_url}
                alt={video.title}
                width={300}
                height={200}
                className="w-full h-48 object-cover rounded-t"
              />
              <div className="p-3">
                <h4 className="font-medium text-sm line-clamp-2">{video.title}</h4>
                <p className="text-caption text-xs text-muted-foreground line-clamp-1">
                  {video.description}
                </p>
                <div className="mt-2 flex justify-between text-xs">
                  <span>{video.duration}</span>
                  <span>{video.license_type.toUpperCase()} • ${video.price}</span>
                </div>
              </div>
            </Card>
          ))}
          {hasMore && !loading && (
            <div key="load-more-videos" className="col-span-full flex justify-center py-4">
              <button onClick={loadMore} className="text-sm text-primary hover:underline">
                Load more
              </button>
            </div>
          )}
        </div>
      )}

      {/* No results state */}
      {!loading && ((mediaType === "image" && images.length === 0) || (mediaType === "video" && videos.length === 0)) && query.length > 0 && (
        <div className="py-8 text-center text-muted-foreground">
          <Loader2 className="mx-auto mb-2" />
          <p>No results found for "{query}"</p>
        </div>
      )}
    </div>
  );
}