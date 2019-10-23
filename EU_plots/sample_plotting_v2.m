clear all;
close all;
%%
subject = 565; % difficult patients: 620->0/565->0    easy patients: 1096->4/590->j=4, 442, 1077, 970
start_j = 4;
end_j = 8;
mode = "graphL"; % raw or graphL
normal_all_W = nan;
normal_flag = false;
save_j = start_j-1;
cluster_ref = 'no-change'; % 'no-change'  'individual', 'all-ictals', 'shown-ictals','shown-interictals' 
fig_counter = 1;
while(save_j<=end_j)
    j = save_j;
    while(j<end_j)
        j = j + 1;
        try
            loaded = load(strcat(num2str(subject),strcat("/matW_0_", strcat(num2str(j),strcat("W_", strcat(mode, "_correlation"))))));
            all_W = loaded.mat;
            labels = loaded.labels;
            diffs = find(diff(labels)~=0);
            if(~isempty(diffs) && j>0 && normal_flag)
                sz_onset = diffs(1)+1;
                sz_offset = diffs(2);
                SOZ = loaded.SOZ;
                save_j = j;
                break;
            elseif(isempty(diffs))
                normal_all_W = all_W;
                normal_flag = true;
            end
        catch
             save_j = save_j+1; 
        end
    end
    if(j==end_j)
        return;
    end

    interictal_len = size(normal_all_W,1);
    all_W = cat(1, normal_all_W, all_W);
    labels = cat(2, zeros(1,interictal_len), labels);
    sz_onset = sz_onset + interictal_len;
    sz_offset = sz_offset + interictal_len;

    [I, N, ~] = size(all_W);
    num_plots = 15;
    if(sz_onset~=-1)
        szr_interval = ceil((sz_offset-sz_onset)/(num_plots-10));
        normal_interval = ceil((interictal_len)/(6));
        ictal_indices = sz_onset:szr_interval:sz_offset-1;
        indices = unique([1:normal_interval:interictal_len-1, interictal_len:4:sz_onset-1, ictal_indices, sz_offset]);
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
    
%% Binarization
    if(false)
        zeros_idx = abs(all_W)<abs(max(all_W(:))/3);
        all_W = ones(size(all_W));
        all_W(zeros_idx) = 0;
    end
%% Clustering
    
    if(strcmp(cluster_ref, 'all-ictals'))
        X = squeeze(mean(all_W(sz_onset:sz_offset,:,:),1));
        reordered_idx = graph_clustering(X);
    elseif(strcmp(cluster_ref, 'all-interictals'))
        X = squeeze(mean(all_W(sz_onset:sz_offset,:,:),1));
        reordered_idx = graph_clustering(X);
    elseif(strcmp(cluster_ref, 'shown-ictals'))
        X = squeeze(mean(all_W(ictal_indices,:,:),1));
        reordered_idx = graph_clustering(X);
    end
    %% Graph Partitioning
    if(false)
        G = graph(A,'omitselfloops');
        p = plot(G,'XData',xy(:,1),'YData',xy(:,2),'Marker','.');
        axis equal
    end
    %% Plotting 
    if(fig_counter<3)
        fig_counter = fig_counter + 1;
        continue;
    end
    fig = figure('units','inch','position',[2,4,7,4.5]); % 7,4.5
    set(gcf,'color','w');
    %     set(gca,'Units','pixels'); %changes the Units property of axes to pixels
    %     set(gca,'Position',[1 1 1024 1024]) 
    
    num_graphs = length(indices);
    num_cols = 5;
    num_rows = ceil(num_graphs/num_cols);
    for i= 1:num_graphs
        real_i = indices(i);
        subplot(num_rows,num_cols,i);
        X = squeeze(all_W(indices(i),:,:));
        if(strcmp(cluster_ref, 'individual'))
            reordered_idx = graph_clustering(X);
        end
        try
            X = X(reordered_idx,reordered_idx);
        catch
        end
        imagesc(X);
        set(gca,'XTick',[]);
        set(gca,'YTick',[]);
        if(real_i<interictal_len)
            title(sprintf('interictal %d',i));
        elseif(real_i<sz_onset)
             title(strcat('\color{blue}', sprintf('preictal %d',i)));
        elseif(real_i==sz_onset)
            title('\color{red} seizure started');
        elseif(real_i<sz_offset)
             title(strcat('\color{red}', sprintf('ictal %d',i)));
        elseif(real_i==sz_offset)
            title('\color{red} seizure ended');
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
    colorbar('Position', [hp4(1)+hp4(3)+0.03  hp4(2)  0.02  (hp4(3)*2.13)*(num_rows)])
    fig_counter = fig_counter +1;
    export_fig([char(strcat(strcat(strcat('C:/Users/Nafiseh Ghoroghchian/OneDrive/research/Graph Signal Processing/Graph Learning/_Rep Graph Learning tex files/sample_',mode),'_'),num2str(subject))),'.png'] ,'-zbuffer','-r1000'); %num2str(j)
end
