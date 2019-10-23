function [ reordered_idx ] = graph_clustering( X )
    [N,~] = size(X);
    max_num_cluster = 4;
    X = max(X(:))- abs(X); % X should be a dissimilarity matrix
    X = X - diag(diag(X));
    y = squareform(X);
    Z = linkage(y);
    % figure();
    % dendrogram(Z)
    A = cluster(Z,'maxclust',max_num_cluster);
    %   A = cluster(Z,'cutoff',0.61);
    % sort orders
    [As, Ai] = sort(A);
    [Bs, Bi] = sort(1:N);
    reordered_idx(Ai) = Bi;

end

