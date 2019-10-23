clear all;
close all;
%%
subject = 442; % difficult patients: 620->0/565->0    easy patients: 1096->4, 590->j=4, 1077, 442
mode = "graphL"; % raw or graphL
for j = 0:15
    try
        loaded = load(strcat(num2str(subject),strcat("/matW_0_", strcat(num2str(j),strcat("W_", strcat(mode, "_correlation"))))));
        all_W = loaded.mat;
        labels = loaded.labels;
        diffs = find(diff(labels)~=0);
        if(size(diffs)~=0)
            sz_onset = diffs(1)+1;
            sz_offset = diffs(2);
            SOZ = loaded.SOZ;
        else
            sz_onset = -1;
            sz_offset = -1;
        end
    catch
         continue; 
    end
    
    [I, N, ~] = size(all_W);
%% Binarization
    if(false)
        zeros_idx = abs(all_W)<abs(max(all_W(:))/3);
        all_W = ones(size(all_W));
        all_W(zeros_idx) = 0;
    end
% Clustering
    if(false)
        max_num_cluster = 5;
    %     for i= 1:I
    %         try
    %             X = squeeze(all_W(sz_onset,:,:)); 
    %         catch
    %             X = squeeze(all_W(1,:,:)); 
    %         end
            X = squeeze(mean(all_W(sz_onset:sz_offset,:,:),1));
            X = max(X(:))- abs(X); % X should be a dissimilarity matrix
            X = X - diag(diag(X));
            y = squareform(X);
            Z = linkage(y,'average');
            figure();
            dendrogram(Z)
    %         A = cluster(Z,'maxclust',max_num_cluster);
            A = cluster(Z,'cutoff',0.61);
            % sort orders
            [As, Ai] = sort(A);
            [Bs, Bi] = sort(1:N);
            reordered_idx(Ai) = Bi;
    %         X_new = X(reordered_idx,reordered_idx);
    %     end
    end
%% Graph Partitioning
    if(false)
        G = graph(A,'omitselfloops');
        p = plot(G,'XData',xy(:,1),'YData',xy(:,2),'Marker','.');
        axis equal
    end
%% Plotting   
    fig = figure('units','inch','position',[2,4,7,4.5]);
    set(gcf,'color','w');
%     set(gca,'Units','pixels'); %changes the Units property of axes to pixels
%     set(gca,'Position',[1 1 1024 1024]) 
    num_plots = 15;
    if(sz_onset~=-1)
        szr_interval = ceil((sz_offset-sz_onset)/(num_plots-10));
        ictal_indices = sz_onset+1:szr_interval:sz_offset-1;
        indices = unique([1:4:sz_onset, ictal_indices, sz_offset, sz_offset+1:2:I]);
        if(length(indices)<num_plots)
            new_indices = sz_onset+2:szr_interval:sz_offset-2;
            indices = [indices, new_indices(1:num_plots-length(indices))];
        elseif(length(indices)>num_plots)
            indices(1:length(indices)-num_plots)=[]; 
        end
    else
        indices = ceil(rand(num_plots)*I);
    end
    indices = sort(indices);
    num_graphs = length(indices);
    num_cols = 5;
    num_rows = ceil(num_graphs/num_cols);
    for i= 1:num_graphs
        real_i = indices(i);
        subplot(num_rows,num_cols,i);
        X = squeeze(all_W(indices(i),:,:));
        try
            X = X(reordered_idx,reordered_idx);
        catch
        end
        imagesc(X);
        set(gca,'XTick',[]);
        set(gca,'YTick',[]);
        if(real_i<sz_onset)
             title(strcat('\color{blue}', sprintf('preictal %d',i)));
        elseif(real_i==sz_onset)
            title('\color{red} seizure started');
        elseif(real_i<sz_offset)
             title(strcat('\color{red}', sprintf('ictal %d',i)));
        elseif(real_i==sz_offset)
            title('\color{red} seizure ended');
        else
             title(sprintf('interictal %d',i));
        end
        fprintf('i=%d, index=%d\n', i, indices(i));
    end
    newmap = jet;                    %starting map
    ncol = size(newmap,1);           %how big is it?
    zpos = 1 + floor(2/3 * ncol);    %2/3 of way through
    newmap(zpos,:) = [1 1 1];        %set that position to white
    colormap(newmap);                %activate it
    subplot(num_rows,num_cols,num_cols*num_rows);
    set(gca,'XTick',[]);
    set(gca,'YTick',[]);
    hp4 = get(subplot(num_rows,num_cols,num_cols*num_rows),'Position');
%     colorbar('Position', [hp4(1)+hp4(3)+0.01  hp4(2)  0.02  hp4(3)*(num_rows)-0.05])
    colorbar('Position', [hp4(1)+hp4(3)+0.02  hp4(2)  0.02  (hp4(3)*2.13)*(num_rows)])
    
%     export_fig([strcat(strcat(strcat('C:/Users/Nafiseh Ghoroghchian/OneDrive/research/Graph Signal Processing/Graph Learning/_Rep Graph Learning tex files/sample_',mode),'_'),strcat(num2str(subject),strcat('_',num2str(j)))),'.png'] ,'-zbuffer','-r1000');
end
